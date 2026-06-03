from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides one AsyncSession per HTTP request.

    The session lifecycle:
    1. Created at the start of the request (when Depends(get_db) resolves)
    2. Yielded to the route handler (and all dependencies that use it)
    3. On success: committed
    4. On any exception: rolled back
    5. Closed (returned to the pool) after the response is sent

    Using `async with AsyncSessionLocal() as session` is equivalent to:
        session = AsyncSessionLocal()
        try:
            yield session
        finally:
            await session.close()  # returns connection to pool

    We add explicit commit/rollback on top.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
