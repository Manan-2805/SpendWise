import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

logger = structlog.get_logger()
SLOW_QUERY_THRESHOLD_MS = 200

engine: AsyncEngine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_timeout=30,
    hide_parameters=True,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def run_after_commit(session: AsyncSession) -> None:
    for callback in session.info.pop("spendwise_after_commit", ()):
        try:
            await callback()
        except Exception as exc:
            logger.error("after_commit_failed", error_type=type(exc).__name__)


def after_commit(
    session: AsyncSession, callback: Callable[[], Awaitable[None]]
) -> None:
    session.info.setdefault("spendwise_after_commit", []).append(callback)


def setup_db_observability(async_engine: AsyncEngine) -> None:
    sync_engine = async_engine.sync_engine

    @event.listens_for(sync_engine, "before_cursor_execute")
    def before_cursor_execute(
        conn: Any,
        _cursor: Any,
        _statement: str,
        _parameters: Any,
        _context: Any,
        _executemany: bool,
    ) -> None:
        conn.info.setdefault("query_start_time", []).append(time.perf_counter())

    @event.listens_for(sync_engine, "after_cursor_execute")
    def after_cursor_execute(
        conn: Any,
        _cursor: Any,
        _statement: str,
        _parameters: Any,
        _context: Any,
        executemany: bool,
    ) -> None:
        if not conn.info.get("query_start_time"):
            return
        start_time = conn.info["query_start_time"].pop(-1)
        duration_ms = (time.perf_counter() - start_time) * 1000

        if duration_ms > SLOW_QUERY_THRESHOLD_MS:
            logger.warning(
                "slow_database_query",
                duration_ms=round(duration_ms, 2),
                executemany=executemany,
            )

    @event.listens_for(sync_engine, "handle_error")
    def handle_error(exception_context: Any) -> None:
        connection = exception_context.connection
        if connection is not None and connection.info.get("query_start_time"):
            connection.info["query_start_time"].pop()
        logger.error(
            "database_error",
            error_type=type(exception_context.original_exception).__name__,
        )


setup_db_observability(engine)
