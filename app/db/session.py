"""
SQLAlchemy async engine and session factory.

The engine is the connection pool — one engine per application process.
The session is a unit of work — one session per HTTP request.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

# Engine — the connection pool
engine: AsyncEngine = create_async_engine(
    # Connection string
    # Must use postgresql+asyncpg:// — not postgresql://
    # asyncpg is the native async PostgreSQL driver
    # The ASYNC_DATABASE_URL computed field in Settings handles this conversion
    settings.ASYNC_DATABASE_URL,
    # Connection pool settings
    # pool_size: number of "permanent" connections kept open
    # These are always available — no wait time
    pool_size=settings.DATABASE_POOL_SIZE,
    # max_overflow: additional connections created under high load
    # Total possible connections = pool_size + max_overflow
    # These are created on demand and closed when returned to the pool
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    # pool_pre_ping: before giving a connection to your code,
    # sends a lightweight "SELECT 1" to verify it is alive.
    # Prevents "connection already closed" errors after PostgreSQL restarts
    # or network appliances drop idle connections.
    # Cost: one extra round-trip per checkout — worth it.
    pool_pre_ping=True,
    # pool_recycle: maximum age (seconds) of a connection before recycling.
    # After 1 hour, the connection is closed and replaced with a fresh one.
    # Prevents issues with stale connections in cloud environments (AWS RDS,
    # GCP Cloud SQL) that drop idle connections after a timeout.
    pool_recycle=3600,
    # pool_timeout: how long to wait (seconds) for a connection from the pool
    # if all connections are busy. Raises TimeoutError after this.
    # Default 30 seconds — fine for most applications.
    pool_timeout=30,
    # echo: log every SQL statement to stdout.
    # Set this from settings.DEBUG — never True in production.
    # WARNING: SQL logs can contain sensitive data (user emails, amounts).
    echo=settings.DEBUG,
    # echo_pool: log connection pool events (checkout, return, creation).
    # Useful for debugging pool exhaustion issues.
    echo_pool=settings.DEBUG,
)

# Session factory — creates new sessions
AsyncSessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    # THE MOST IMPORTANT SETTING IN ASYNC SQLALCHEMY
    # expire_on_commit=False
    #
    # What expire_on_commit does by default (True):
    # After session.commit(), SQLAlchemy marks every loaded attribute
    # as "expired" — stale. On the next access, it re-fetches from DB.
    #
    # In synchronous SQLAlchemy this is transparent — the re-fetch
    # happens automatically on attribute access.
    #
    # In async SQLAlchemy, that re-fetch is an async I/O operation
    # that cannot happen implicitly. When you access an expired attribute
    # outside an async context, you get:
    # sqlalchemy.exc.MissingGreenlet: greenlet_spawn has not been called
    # Setting expire_on_commit=False keeps attribute values in memory
    # after commit. The data you just committed is still accessible —
    # no re-fetch needed. This is correct for HTTP request handlers:
    # you commit at the end of the request and immediately return the
    # data — you never need to re-read it from the database.
    expire_on_commit=False,
    # autoflush=False: don't automatically flush (write to DB) before
    # every query. We flush manually with session.flush() when we need
    # to get generated IDs before committing.
    # Manual control is safer in complex transactions.
    autoflush=False,
    # autocommit=False: we manage transactions explicitly.
    # Every session starts in a transaction, committed or rolled back
    # by our dependency function.
    autocommit=False,
)


# Session dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency — one session per request.
    Commits on success, rolls back on exception.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
