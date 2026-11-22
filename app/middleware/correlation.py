import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """
    Add a correlation ID to every request.

    It reads from X-Correlation-ID header if present, or generates a new UUID.
    Stores the ID in request.state for access in route handlers and dependencies.
    Also sets X-Correlation-ID response header for downstream propagation.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Extract or generate correlation ID
        supplied_id = request.headers.get("X-Correlation-ID", "")
        try:
            correlation_id = str(uuid.UUID(supplied_id))
        except ValueError:
            correlation_id = str(uuid.uuid4())

        # Store in request.state for access in routes/dependencies
        request.state.correlation_id = correlation_id

        # Bind to structlog contextvars so every log line includes it
        import structlog

        with structlog.contextvars.bound_contextvars(correlation_id=correlation_id):
            response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response
