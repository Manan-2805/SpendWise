# pyright: reportUnusedFunction=false
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import SpendWiseError
from app.core.logging import configure_logging
from app.core.rate_limit import custom_rate_limit_handler, limiter


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application startup and shutdown events.

    Lifespan is the modern replacement for @app.on_event("startup") and
    @app.on_event("shutdown"). Code before `yield` runs at startup.
    Code after `yield` runs at shutdown — even if the process is killed
    (provided it receives a SIGTERM/SIGINT signal).

    This pattern is async-native and type-safe.
    """
    # Startup
    configure_logging(debug=settings.DEBUG)

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.db.session import engine

    # Fail fast at startup if the database is unreachable.
    # Better to crash now than to discover it on the first request.
    try:
        async with AsyncSession(engine) as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        import structlog

        structlog.get_logger().critical(
            "database_connection_failed",
            error=str(e),
        )
        raise

    import structlog

    structlog.get_logger().info(
        "application_started",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )

    yield

    # Shutdown
    from app.db.session import engine

    await engine.dispose()

    import structlog

    structlog.get_logger().info("application_shutdown")


def create_application() -> FastAPI:
    """
    Application factory — creates and configures the FastAPI instance.

    Each call creates a fresh instance. This is used in testing
    and in the module-level `app` singleton.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        description="Personal expense tracker REST API",
        version=settings.APP_VERSION,
        # Hide interactive docs in production — reduces attack surface
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # Middleware registration (ORDER MATTERS)
    # Middleware executes in REVERSE order of registration.
    # We add CORS first (it should run last on the way in), then
    # our custom middleware in the order we want them to run last→first.
    # For request lifecycle: custom middleware → CORS → route handler
    # For response: route handler → CORS → custom middleware

    # CORS — must be registered first in code but runs last in the chain
    # This ensures CORS headers are added to responses even if an
    # exception occurs in later middleware.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "X-Correlation-ID",
            "X-Requested-With",
        ],
        expose_headers=["X-Process-Time", "X-Correlation-ID"],
        max_age=600,
    )

    # Custom middleware — added after CORS so they run before it
    # (Full implementations in sections 5 and 9 of this part)
    # Attach limiter to app.state so it can be accessed by middleware
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)  # type: ignore[arg-type]

    # Add the SlowAPIMiddleware - this applies any default_limits
    application.add_middleware(SlowAPIMiddleware)
    from app.middleware.correlation import CorrelationIDMiddleware
    from app.middleware.logging import RequestLoggingMiddleware
    from app.middleware.timing import RequestTimingMiddleware

    application.add_middleware(CorrelationIDMiddleware)
    application.add_middleware(RequestTimingMiddleware)
    application.add_middleware(RequestLoggingMiddleware)

    # ── Routers ──────────────────────────────────────────────────
    application.include_router(
        api_v1_router,
        prefix=settings.API_V1_PREFIX,
    )

    # ── Health check endpoint (public, no authentication) ────────
    @application.get("/health", tags=["Health"], include_in_schema=settings.DEBUG)
    async def health() -> dict[str, Any]:
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    # ── Exception handlers (register AFTER routers) ──────────────
    # Exception handlers follow specificity order: most specific first.
    # SpendWiseError is a base class — handles all domain exceptions.
    # RequestValidationError handles Pydantic validation failures.
    # Exception is the catch-all for unexpected errors.
    # Registering after routers ensures they override any router-level handlers.

    # 1. Domain exceptions (most specific — registered first)
    @application.exception_handler(SpendWiseError)
    async def spendwise_exception_handler(
        request: Request, exc: SpendWiseError
    ) -> JSONResponse:
        """Convert SpendWise domain exceptions to HTTP responses."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "code": exc.code,
                # Optional: correlation_id from request.state
                "request_id": getattr(request.state, "correlation_id", None),
            },
        )

    # 2. Pydantic validation errors (medium specificity)
    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Convert Pydantic validation errors to a consistent format."""
        errors: list[dict[str, Any]] = []
        for error in exc.errors():
            field: str = ".".join(str(loc) for loc in error["loc"] if loc != "body")
            errors.append(
                {
                    "field": field,
                    "message": error["msg"],
                    "type": error["type"],
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Request validation failed",
                "code": "VALIDATION_ERROR",
                "errors": errors,
            },
        )

    # 3. Catch-all for unexpected exceptions (least specific)
    @application.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, _: Exception
    ) -> JSONResponse:
        """
        Catch-all for unexpected exceptions.
        Never leak stack traces or internal details in production.
        """
        import structlog

        structlog.get_logger().exception(
            "unhandled_exception",
            path=str(request.url.path),
            method=request.method,
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An unexpected error occurred",
                "code": "INTERNAL_SERVER_ERROR",
            },
        )

    return application


# Module-level app instance — what uvicorn/gunicorn imports
app: FastAPI = create_application()
