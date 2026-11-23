"""Collect local benchmark measurements without changing the application."""

import asyncio
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from redis import Redis
from redis.asyncio import Redis as AsyncRedis
from sqlalchemy import event

from app.db.session import engine
from app.main import app as application
from app.services import auth
from scripts.run_capacity_test import percentile

samples: dict[str, list[float]] = defaultdict(list)
slow_queries: dict[str, list[float]] = defaultdict(list)
sql_tables = re.compile(r"\b(?:FROM|INTO|UPDATE)\s+(\w+)", re.IGNORECASE)
pool = engine.sync_engine.pool
original_connect = pool.connect
# SQLAlchemy's local queue has no public wait timing hook.
queue = pool._pool
original_queue_get = queue.get
original_redis = Redis.execute_command
original_async_redis = AsyncRedis.execute_command
original_verify = auth.verify_password


def connect() -> Any:
    started = time.perf_counter()
    try:
        return original_connect()
    finally:
        samples["db_checkout_ms"].append((time.perf_counter() - started) * 1000)


def queue_get(block: bool, timeout: float | None) -> Any:
    if not block:
        return original_queue_get(block, timeout)
    started = time.perf_counter()
    try:
        return original_queue_get(block, timeout)
    finally:
        samples["db_pool_wait_ms"].append((time.perf_counter() - started) * 1000)


def redis_command(client: Redis, *args: Any, **kwargs: Any) -> Any:
    started = time.perf_counter()
    try:
        return original_redis(client, *args, **kwargs)
    finally:
        samples["redis_sync_ms"].append((time.perf_counter() - started) * 1000)


async def async_redis_command(client: AsyncRedis, *args: Any, **kwargs: Any) -> Any:
    started = time.perf_counter()
    try:
        return await original_async_redis(client, *args, **kwargs)
    finally:
        samples["redis_async_ms"].append((time.perf_counter() - started) * 1000)


def verify(*args: Any) -> bool:
    has_event_loop = True
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        has_event_loop = False

    started = time.perf_counter()
    cpu_start = time.thread_time()
    try:
        return original_verify(*args)
    finally:
        key = "bcrypt_loop_ms" if has_event_loop else "bcrypt_thread_ms"
        samples[key].append((time.perf_counter() - started) * 1000)
        samples["bcrypt_cpu_ms"].append((time.thread_time() - cpu_start) * 1000)


@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_sql(_conn, _cursor, _statement, _parameters, context, _executemany):
    context.capacity_started = time.perf_counter()


@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_sql(_conn, _cursor, statement, _parameters, context, _executemany):
    elapsed = (time.perf_counter() - context.capacity_started) * 1000
    samples["sql_ms"].append(elapsed)
    if elapsed >= 50:
        table = sql_tables.search(statement)
        operation = statement.split(maxsplit=1)[0].upper()
        slow_queries[f"{operation} {table[1] if table else '-'}"].append(elapsed)


def summarize(values: list[float]) -> dict[str, float | int | None]:
    return {
        "n": len(values),
        "p95": percentile(values),
        "max": round(max(values), 2),
        "total": round(sum(values), 2),
    }


pool.connect = connect
queue.get = queue_get
Redis.execute_command = redis_command
AsyncRedis.execute_command = async_redis_command
auth.verify_password = verify


async def app(scope, receive, send) -> None:
    try:
        await application(scope, receive, send)
    finally:
        if scope["type"] == "lifespan":
            report = {name: summarize(values) for name, values in samples.items()}
            report["sql_50ms_or_more"] = {
                route: summarize(values) for route, values in slow_queries.items()
            }
            path = Path(os.environ["CAPACITY_STATS_DIR"]) / f"{os.getpid()}.json"
            path.write_text(json.dumps(report), encoding="utf-8")
