import time
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
    echo=settings.DEBUG,
)

AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


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
        statement: str,
        parameters: Any,
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
                statement=statement.replace("\n", " ")[:500],
                parameters=str(parameters)[:200],
                executemany=executemany,
            )

    @event.listens_for(sync_engine, "handle_error")
    def handle_error(exception_context: Any) -> None:
        logger.error(
            "database_error",
            original_exception=str(exception_context.original_exception),
            statement=str(exception_context.statement)[:500],
        )


setup_db_observability(engine)
