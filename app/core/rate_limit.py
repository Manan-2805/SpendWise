from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

# Create the limiter with a Redis backend for distributed deployments
limiter = Limiter(
    key_func=get_remote_address,  # Identify clients by IP address
    storage_uri=str(settings.REDIS_URL),  # Redis URL - must support async
    default_limits=["100/minute"],  # Global fallback limit (overridden per route)
    strategy="fixed-window",  # Fixed window algorithm (simplest)
)


# Override the default 429 response to match SpendWise's error format
def custom_rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Too many requests - please slow down",
            "code": "RATE_LIMIT_EXCEEDED",
            "retry_after": getattr(exc, "retry_after", None),
        },
    )
