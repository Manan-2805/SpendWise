"""Run the open-loop mixed workload against a local two-worker Granian API."""

import argparse
import asyncio
import json
import math
import os
import random
import re
import secrets
import signal
import subprocess
import sys
from collections import Counter, defaultdict
from contextlib import contextmanager, suppress
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from urllib.parse import urlsplit

import httpx

from scripts.run_load_test import wait_for_api

WORKERS = 2
STATUS_TIMEOUT = 3
PROBE_INTERVAL = 1
PROBE_TIMEOUT = 1


def operation_order() -> list[str]:
    order = ["transactions"] * 44 + ["report"] * 43 + ["write"] * 12 + ["login"]
    random.Random(42).shuffle(order)
    return order


def transaction_payload(category: int, today: date) -> dict[str, int | str]:
    return {
        "amount": "10.00",
        "category_id": category,
        "description": "Capacity workload transaction",
        "transaction_date": today.isoformat(),
        "type": "expense",
    }


def percentile(values: list[float]) -> float | None:
    if values:
        return round(sorted(values)[math.ceil(len(values) * 0.95) - 1], 2)
    return None


def local_environment() -> dict[str, str]:
    urls = urlsplit(os.environ["REDIS_URL"])
    return os.environ | {
        "ENVIRONMENT": "development",
        "DEBUG": "false",
        "SECRET_KEY": secrets.token_hex(32),
        "RATE_LIMIT_DEFAULT": "1000000/minute",
        "RATE_LIMIT_LOGIN": "1000000/minute",
        "SMTP_HOST": "",
        "REDIS_URL": urls._replace(path="/3").geturl(),
        "CELERY_BROKER_URL": urls._replace(path="/4").geturl(),
        "CELERY_RESULT_BACKEND": urls._replace(path="/5").geturl(),
    }


async def accounts(count: int) -> list[tuple[str, int, str]]:
    from sqlalchemy import select

    from app.core.security import create_access_token
    from app.db.session import AsyncSessionLocal, engine
    from app.models.category import Category
    from app.models.user import User

    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(User.id, User.email, User.auth_version, Category.id)
                .join(Category, Category.user_id == User.id)
                .where(
                    User.username.startswith("capacity_user_", autoescape=True),
                    Category.name == "Food & Dining",
                )
                .order_by(User.id)
                .limit(count)
            )
        ).all()
    await engine.dispose()
    if len(rows) != count:
        raise RuntimeError("Capacity accounts are missing. Run make seed-capacity.")
    return [
        (email, category, create_access_token(subject=user, auth_version=version))
        for user, email, version, category in rows
    ]


@contextmanager
def process(command: list[str], env: dict[str, str], stdout=subprocess.DEVNULL):
    with subprocess.Popen(
        command, env=env, stdout=stdout, start_new_session=True
    ) as child:
        try:
            yield child
        finally:
            if child.poll() is None:
                child.terminate()
                with suppress(subprocess.TimeoutExpired):
                    child.wait(timeout=10)
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGKILL)


def process_ticks(api: int, celery: int) -> dict[str, int]:
    result = {}
    for path in Path("/proc").glob("[0-9]*/stat"):
        try:
            command, fields = path.read_text().rsplit(") ", 1)
        except (OSError, ValueError):
            continue
        name = command.partition("(")[2]
        state, parent, *rest = fields.split()
        pid = int(path.parent.name)
        names = {os.getpid(): "generator", api: "api-parent", celery: "celery-parent"}
        label = names.get(pid)
        if int(parent) == api:
            label = "api-worker"
        elif int(parent) == celery:
            label = "celery-worker"
        elif name in {"postgres", "redis-server"}:
            label = name
        if label and state != "Z":
            result[f"{label}:{pid}"] = int(rest[9]) + int(rest[10])
    return result


def container_cpu(text: str) -> dict[str, dict[str, float]]:
    samples: dict[str, list[float]] = defaultdict(list)
    cleaned = re.sub(r"\x1b\[[0-9;]*[HJ]", "", text)
    for name, cpu in re.findall(r"([\w.-]+)\s+(\d+(?:\.\d+)?)%", cleaned):
        samples[name].append(float(cpu))
    return {
        name: {"mean": round(sum(values) / len(values), 2), "peak": max(values)}
        for name, values in samples.items()
    }


async def measure(rate, seconds, base_url, identities, api_pid, celery_pid):
    from scripts.seed_load_test_db import SEED_PASSWORD

    order = operation_order()
    today = date.today()
    paths = {
        "transactions": "/transactions/?per_page=20",
        "report": f"/reports/monthly-summary?year={today.year}&month={today.month}",
    }
    latencies: dict[str, list[float]] = defaultdict(list)
    statuses: Counter[str] = Counter()
    probes: dict[str, Counter[str]] = defaultdict(Counter)
    pending: set[asyncio.Task] = set()
    cpu_ticks: Counter[str] = Counter()
    earlier = process_ticks(api_pid, celery_pid)
    issued = 0
    fast_rejections = 0
    start = perf_counter()
    end = start + seconds

    async def request(shard_index, index, scheduled):
        nonlocal issued, fast_rejections
        if perf_counter() >= end:
            return
        issued += 1
        shard = shards[shard_index]
        operation = order[index % len(order)]
        email, category, token = identities[index % rate]
        status = "timeout"
        try:
            async with asyncio.timeout(STATUS_TIMEOUT):
                if operation == "login":
                    response = await login_shards[shard_index].post(
                        "/auth/login", json={"email": email, "password": SEED_PASSWORD}
                    )
                elif operation == "write":
                    response = await shard.post(
                        "/transactions/",
                        headers={"Authorization": f"Bearer {token}"},
                        json=transaction_payload(category, today),
                    )
                else:
                    response = await shard.get(
                        paths[operation], headers={"Authorization": f"Bearer {token}"}
                    )
                status = str(response.status_code)
                if response.status_code == 503 and "retry-after" in response.headers:
                    fast_rejections += 1
        except (httpx.TimeoutException, TimeoutError):
            pass
        except httpx.TransportError:
            status = "transport_error"
        latencies[operation].append((perf_counter() - scheduled) * 1000)
        statuses[status] += 1

    async def probe(path, scheduled):
        await asyncio.sleep(max(0, scheduled - perf_counter()))
        try:
            async with asyncio.timeout(PROBE_TIMEOUT):
                response = await probe_client.get(f"/health/{path}")
                probes[path][str(response.status_code)] += 1
                if (
                    path == "ready"
                    and response.status_code == 503
                    and response.headers.get("content-type", "").startswith(
                        "application/json"
                    )
                ):
                    result = response.json()
                    for key in ("db", "redis", "celery"):
                        if result.get(key) == "down":
                            probes[path][f"{key}_down"] += 1
        except (httpx.TransportError, TimeoutError):
            probes[path]["transport_error"] += 1

    async def monitor_cpu():
        nonlocal earlier
        for index in range(1, math.ceil(seconds) + 1):
            await asyncio.sleep(max(0, min(start + index, end) - perf_counter()))
            later = process_ticks(api_pid, celery_pid)
            for name, ticks in later.items():
                cpu_ticks[name] += ticks - earlier.get(name, ticks)
            earlier = later

    limits = httpx.Limits(max_connections=512, max_keepalive_connections=256)
    shards = [httpx.AsyncClient(base_url=base_url, limits=limits) for _ in range(8)]
    login_shards = [httpx.AsyncClient(base_url=base_url) for _ in shards]
    async with httpx.AsyncClient(base_url=base_url) as probe_client:
        try:
            probe_count = math.ceil(seconds / PROBE_INTERVAL)
            monitoring = asyncio.gather(
                monitor_cpu(),
                *(
                    probe(path, start + index * PROBE_INTERVAL)
                    for index in range(probe_count)
                    for path in ("live", "ready")
                ),
            )
            scheduled_count = int(rate * seconds)
            for index in range(scheduled_count):
                scheduled = start + index / rate
                now = perf_counter()
                if now >= end:
                    break
                await asyncio.sleep(max(0, scheduled - now))
                if (
                    perf_counter() - scheduled < 1
                    and len(pending) < rate * STATUS_TIMEOUT
                ):
                    task = asyncio.create_task(
                        request(
                            (index // rate + index) % len(shards),
                            index,
                            scheduled,
                        )
                    )
                    pending.add(task)
                    task.add_done_callback(pending.discard)
            await monitoring
            await asyncio.gather(*pending)
        finally:
            await asyncio.gather(
                *(shard.aclose() for shard in (*shards, *login_shards))
            )

    success = sum(count for status, count in statuses.items() if status.startswith("2"))
    p95 = percentile([value for samples in latencies.values() for value in samples])
    error_pct = round(100 * (issued - success) / issued, 2) if issued else 100.0
    issued_pct = round(100 * issued / scheduled_count, 2)
    live_pct = round(100 * probes["live"]["200"] / probe_count, 2)
    ready_pct = round(100 * probes["ready"]["200"] / probe_count, 2)
    clock_ticks = os.sysconf("SC_CLK_TCK")
    return {
        "target_req_s": rate,
        "scheduled": scheduled_count,
        "issued": issued,
        "issued_pct": issued_pct,
        "success": success,
        "successful_req_s": round(success / seconds, 2),
        "p95_ms": p95,
        "error_pct": error_pct,
        "live_pct": live_pct,
        "ready_pct": ready_pct,
        "pass": p95 is not None
        and p95 <= 500
        and error_pct <= 1
        and issued_pct >= 95
        and min(live_pct, ready_pct) >= 98,
        "status_counts": dict(statuses),
        "retry_after_503s": fast_rejections,
        "probes": {path: dict(counts) for path, counts in probes.items()},
        "operations": {
            key: {"n": len(values), "p95_ms": percentile(values)}
            for key, values in latencies.items()
        },
        "cpu_pct_of_one_core": {
            name: round(100 * ticks / clock_ticks / seconds, 2)
            for name, ticks in sorted(cpu_ticks.items(), key=lambda item: -item[1])
            if ticks
        },
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rates", nargs="+", type=int, default=[160, 240, 640])
    parser.add_argument("--seconds", type=float, default=120)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if args.seconds < 1 or min(args.rates) < 1 or max(args.rates) > 5000:
        parser.error("Use at least one second and rates in the range 1-5000 req/s")

    env = local_environment()
    os.environ.update(env)
    identities = await accounts(max(args.rates))
    bin_dir = Path(sys.executable).parent
    base_url = f"http://127.0.0.1:{args.port}/api/v1"
    celery_command = [
        str(bin_dir / "celery"),
        "-A",
        "app.worker.celery_app",
        "worker",
        "--loglevel=warning",
        "--concurrency=2",
        "--without-gossip",
        "--without-mingle",
    ]
    api_command = [
        str(bin_dir / "granian"),
        "--interface",
        "asgi",
        "--host",
        "127.0.0.1",
        "--port",
        str(args.port),
        "--workers",
        str(WORKERS),
        "--no-access-log",
        "scripts.capacity_observability:app",
    ]
    container_ids = os.environ["CAPACITY_CONTAINER_IDS"].split()
    stats_command = [
        "docker",
        "stats",
        "--format",
        "{{.Name}} {{.CPUPerc}}",
        *container_ids,
    ]
    print(
        json.dumps(
            {"seconds": args.seconds, "granian_workers": WORKERS, "celery_workers": 2}
        ),
        flush=True,
    )
    with process(celery_command, env) as celery:
        for rate in args.rates:
            with TemporaryDirectory(prefix="spendwise-capacity-") as directory:
                cpu_file = Path(directory) / "container-cpu.txt"
                with process(
                    api_command, env | {"CAPACITY_STATS_DIR": directory}
                ) as api:
                    async with httpx.AsyncClient(
                        base_url=base_url, timeout=1
                    ) as client:
                        await wait_for_api(client, api)
                    with (
                        cpu_file.open("w", encoding="utf-8") as cpu_output,
                        process(stats_command, env, stdout=cpu_output),
                    ):
                        result = await measure(
                            rate,
                            args.seconds,
                            base_url,
                            identities,
                            api.pid,
                            celery.pid,
                        )
                result["container_cpu_pct_of_one_core"] = container_cpu(
                    cpu_file.read_text(encoding="utf-8")
                )
                result["api_workers"] = {
                    path.stem: json.loads(path.read_text(encoding="utf-8"))
                    for path in Path(directory).glob("*.json")
                }
                print(json.dumps(result), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
