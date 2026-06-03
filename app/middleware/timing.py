import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """
    Measures request processing time and adds it to response headers.

    The X-Process-Time header is standard and can be read by load balancers,
    monitoring systems, and client applications.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time

        # Add to response header (in seconds, milliseconds for precision)
        response.headers["X-Process-Time"] = f"{process_time * 1000:.2f}ms"

        # Also log slow requests for alerting
        if process_time > 1.0:  # Slower than 1 second
            import structlog

            structlog.get_logger().warning(
                "slow_request",
                method=request.method,
                path=request.url.path,
                process_time=round(process_time, 3),
                status_code=response.status_code,
            )

        return response
