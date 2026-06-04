from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import SpendWiseError
from app.core.logging import configure_logging
from app.core.rate_limit import custom_rate_limit_handler, limiter
from app.core.redis import close_redis, ping_redis
from app.core.tracing import setup_tracing
from app.db.session import AsyncSessionLocal, engine
from app.middleware.correlation import CorrelationIDMiddleware
from app.middleware.logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.middleware.timing import RequestTimingMiddleware

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """
    Manage application startup and shutdown events.
    """
    # Startup logging and tracing configuration
    configure_logging(debug=settings.DEBUG)
    setup_tracing(application, engine)

    # Fail fast if DB or Redis is down at startup
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        logger.critical("database_connection_failed", error=str(e))
        raise

    redis_ok = await ping_redis()
    if not redis_ok:
        logger.critical("redis_connection_failed")
        raise RuntimeError("Redis connection failed")

    logger.info(
        "application_started",
        app_name=settings.APP_NAME,
        version=settings.APP_VERSION,
        debug=settings.DEBUG,
    )

    yield

    # Shutdown
    await close_redis()
    await engine.dispose()
    logger.info("application_shutdown")


def create_application() -> FastAPI:
    """
    Application factory — creates and configures the FastAPI instance.
    """
    application = FastAPI(
        title=settings.APP_NAME,
        description="Personal expense tracker REST API",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url="/openapi.json" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # CORS configuration
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
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

    # Rate Limiting configuration
    application.state.limiter = limiter
    application.add_exception_handler(RateLimitExceeded, custom_rate_limit_handler)  # type: ignore[arg-type]
    application.add_middleware(SlowAPIMiddleware)

    # Metrics instrumentation
    Instrumentator().instrument(application).expose(
        application, tags=["Metrics"], include_in_schema=settings.DEBUG
    )

    # ASGI Custom Middleware (Order of execution: CorrelationID -> Timing -> Logging -> SecurityHeaders)
    application.add_middleware(SecurityHeadersMiddleware)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_middleware(RequestTimingMiddleware)
    application.add_middleware(CorrelationIDMiddleware)

    # API Routes
    application.include_router(
        api_v1_router,
        prefix=settings.API_V1_PREFIX,
    )

    # Exception mapping rules
    @application.exception_handler(SpendWiseError)
    async def spendwise_exception_handler(
        request: Request, exc: SpendWiseError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
                "code": exc.code,
                "request_id": getattr(request.state, "correlation_id", None),
            },
        )

    @application.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _: Request, exc: RequestValidationError
    ) -> JSONResponse:
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
        logger.exception(
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


app: FastAPI = create_application()
