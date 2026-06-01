"""
SQLAlchemy async engine and session factory.

The engine is the connection pool — one engine per application process.
The session is a unit of work — one session per HTTP request.
"""

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# ── Engine — the connection pool ─────────────────────────────
engine: AsyncEngine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,

    # Verify connections are alive before using them.
    # Prevents "connection already closed" errors after a PostgreSQL restart.
    pool_pre_ping=True,

    # Recycle connections after 1 hour.
    # Prevents issues with idle connections dropped by the database or
    # a network appliance (common in cloud environments).
    pool_recycle=3600,

    # Log SQL statements in debug mode.
    # WARNING: Do not enable in production — logs may contain sensitive data.
    echo=settings.DEBUG,

    # Silence SQLAlchemy's "pool" level logging unless in debug mode.
    echo_pool=settings.DEBUG,
)

# ── Session factory — creates new sessions ───────────────────
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,

    # CRITICAL for async SQLAlchemy:
    # After session.commit(), SQLAlchemy normally expires all attributes
    # so they are re-loaded from the database on next access.
    # In async context, that re-load is a lazy IO operation that fails
    # because there is no implicit async context to run it in.
    # Setting expire_on_commit=False keeps attribute values in memory
    # after commit — no re-load needed.
    expire_on_commit=False,

    autoflush=False,    # We flush manually where needed (gives more control)
    autocommit=False,   # We manage transactions explicitly
)