from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse

from app.core.health import UNAVAILABLE, Readiness
from app.core.rate_limit import limiter

router = APIRouter()


@router.get("/health", summary="Liveness Probe - Simple check")
@limiter.exempt  # type: ignore[untyped-decorator]
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/live", summary="Liveness Probe - Alive status")
@limiter.exempt  # type: ignore[untyped-decorator]
async def liveness() -> dict[str, str]:
    return {"status": "alive"}


@router.get("/health/ready", summary="Readiness Probe - Cached dependency status")
@limiter.exempt  # type: ignore[untyped-decorator]
async def readiness(request: Request) -> JSONResponse:
    monitor: Readiness | None = getattr(request.app.state, "readiness", None)
    db_ok, redis_ok, celery_ok = monitor.current() if monitor else UNAVAILABLE
    ready = db_ok and redis_ok and celery_ok
    return JSONResponse(
        status_code=status.HTTP_200_OK
        if ready
        else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "ready" if ready else "not_ready",
            "db": "up" if db_ok else "down",
            "redis": "up" if redis_ok else "down",
            "celery": "up" if celery_ok else "down",
        },
    )
