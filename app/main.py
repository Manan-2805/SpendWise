# pyright: reportUnusedFunction=false
"""
FastAPI application factory for SpendWise.

Usage:
    Development:  uvicorn app.main:app --reload
    Production:   gunicorn app.main:app --worker-class uvicorn.workers.UvicornWorker
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import SpendWiseError
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application startup and shutdown events.

    Code before `yield` runs on startup (before the first request).
    Code after `yield` runs on shutdown (after the last request).

    This replaces the deprecated @app.on_event("startup") decorator.
    """
    # Startup
    configure_logging(debug=settings.DEBUG)

    # Import here to avoid circular imports during module load
    from app.db.session import engine

    # Verify database connectivity at startup
    # This fails fast if DATABASE_URL is wrong — better than
    # discovering it on the first request
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(engine) as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        import structlog

        structlog.get_logger().critical(
            "database_connection_failed",
            error=str(e),
            database_url=str(settings.DATABASE_URL),
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

    Using a factory function (rather than a module-level `app = FastAPI()`)
    makes testing easier: each test can call create_application() to get
    a fresh instance with overridden dependencies.
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

    # Middleware
    # Middleware is executed in REVERSE order of registration.
    # The last middleware added runs FIRST on incoming requests.
    # We want: CorrelationID → Timing → Logging → CORS → route handler
    # So we add them in: CORS → Logging → Timing → CorrelationID

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
        max_age=600,  # Cache preflight for 10 minutes
    )

    # Custom middleware registered here — implementations in Part 10
    # from app.middleware.logging import RequestLoggingMiddleware
    # from app.middleware.timing import RequestTimingMiddleware
    # from app.middleware.correlation import CorrelationIDMiddleware
    # application.add_middleware(RequestLoggingMiddleware)
    # application.add_middleware(RequestTimingMiddleware)
    # application.add_middleware(CorrelationIDMiddleware)

    # Routers
    # Routers registered here — implementations in Part 6
    # from app.api.v1.router import api_v1_router
    # application.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # Exception Handlers
    @application.exception_handler(SpendWiseError)
    async def spendwise_exception_handler(
        _: Request, exc: SpendWiseError
    ) -> JSONResponse:
        """
        Convert SpendWise domain exceptions to HTTP responses.
        This single handler covers the entire exception hierarchy.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "code": exc.code,
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """
        Convert Pydantic validation errors to a consistent format.
        FastAPI's default format is verbose — we normalise it.
        """
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

    # Health Check
    @application.get("/health", tags=["Health"], include_in_schema=settings.DEBUG)
    async def health() -> dict[str, str]:
        """Shallow health check — confirms the application process is alive."""
        return {
            "status": "healthy",
            "app": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    return application


# Module-level app instance — what uvicorn/gunicorn import
app: FastAPI = create_application()
