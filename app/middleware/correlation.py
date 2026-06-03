import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Pure ASGI middleware that adds a correlation ID to every request.

    It reads from X-Correlation-ID header if present, or generates a new UUID.
    Stores the ID in request.state for access in route handlers and dependencies.
    Also sets X-Correlation-ID response header for downstream propagation.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Extract or generate correlation ID
        correlation_id: str | None = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Store in request.state for access in routes/dependencies
        request.state.correlation_id = correlation_id

        # Bind to structlog contextvars so every log line includes it
        import structlog

        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        # Process the request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response
