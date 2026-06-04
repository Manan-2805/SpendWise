import asyncio

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.redis import ping_redis
from app.db.session import AsyncSessionLocal

router = APIRouter()


async def check_db() -> bool:
    """Check database connectivity."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False


async def check_redis() -> bool:
    """Check Redis connectivity."""
    return await ping_redis()


def check_celery_sync() -> bool:
    """Synchronous connection check for Celery broker."""
    try:
        from app.worker.celery_app import celery_app

        with celery_app.connection_for_write() as conn:
            conn.connect()
            return True
    except Exception:
        return False


async def check_celery() -> bool:
    """Asynchronous wrapper for Celery broker check."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, check_celery_sync)


@router.get("/health", summary="Liveness Probe - Simple check")
async def health() -> dict[str, str]:
    """Shallow liveness probe returning OK."""
    return {"status": "ok"}


@router.get("/health/live", summary="Liveness Probe - Alive status")
async def liveness() -> dict[str, str]:
    """Liveness probe verifying that the process is alive."""
    return {"status": "alive"}


@router.get("/health/ready", summary="Readiness Probe - Deep health check")
async def readiness() -> JSONResponse:
    """Readiness probe verifying DB, Redis, and Celery broker are ready with a 200ms timeout."""
    db_task = asyncio.create_task(check_db())
    redis_task = asyncio.create_task(check_redis())
    celery_task = asyncio.create_task(check_celery())

    # Wait for checks to complete, enforcing a 200ms timeout
    try:
        db_ok = await asyncio.wait_for(db_task, timeout=0.2)
    except (TimeoutError, Exception):
        db_ok = False

    try:
        redis_ok = await asyncio.wait_for(redis_task, timeout=0.2)
    except (TimeoutError, Exception):
        redis_ok = False

    try:
        celery_ok = await asyncio.wait_for(celery_task, timeout=0.2)
    except (TimeoutError, Exception):
        celery_ok = False

    status_code = (
        status.HTTP_200_OK
        if (db_ok and redis_ok and celery_ok)
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ready" if status_code == status.HTTP_200_OK else "not_ready",
            "db": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
            "celery": "up" if celery_ok else "down",
        },
    )
