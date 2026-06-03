import time
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = structlog.get_logger()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        start_time: float = time.perf_counter()

        # Log request start (optional, usually logging at end is enough)

        try:
            response = await call_next(request)
        except Exception as e:
            # We don't log exception details here, let exception handlers do it
            raise e
        finally:
            process_time = time.perf_counter() - start_time
            # Try to get status_code if response is defined
            status_code: Any | int = (
                getattr(response, "status_code", 500) if "response" in locals() else 500
            )

            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                process_time_ms=round(process_time * 1000, 2),
            )

        return response
