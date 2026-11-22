from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=str(settings.REDIS_URL),
    default_limits=[settings.RATE_LIMIT_DEFAULT],
    strategy="fixed-window",
)


def custom_rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests - please slow down",
            "code": "RATE_LIMIT_EXCEEDED",
            "retry_after": getattr(exc, "retry_after", None),
        },
    )
