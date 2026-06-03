"""
Structured logging configuration using structlog.

In development: coloured, human-readable output to console.
In production: JSON output to stdout (collected by your log aggregator).

Usage anywhere in the application:
    import structlog
    log = structlog.get_logger()
    log.info("transaction_created", user_id=1, amount="100.00")
"""

import logging
import sys
from typing import Any

import structlog


def configure_logging(debug: bool = False) -> None:
    """
    Configure structlog and stdlib logging.

    Call this once at application startup (in the lifespan function).
    Subsequent calls are safe but redundant.
    """
    # Shared processors — run on every log event
    shared_processors: list[structlog.types.Processor] = [
        # Merge context variables bound via bind_contextvars()
        # Used for correlation IDs that persist across a request
        structlog.contextvars.merge_contextvars,
        # Add the log level name ("info", "error", etc.)
        structlog.stdlib.add_log_level,
        # Add the logger name (module path)
        structlog.stdlib.add_logger_name,
        # Add ISO 8601 timestamp in UTC
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Render exception info (exc_info=True in log call)
        structlog.processors.StackInfoRenderer(),
    ]

    if debug:
        # Development: pretty-printed, coloured output
        processors: list[Any] = [
            *shared_processors,
            # Format exceptions as strings for console output
            structlog.dev.set_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
        log_level = logging.DEBUG
    else:
        # Production: structured JSON output
        processors = [
            *shared_processors,
            # Convert exception info to a dict for JSON serialisation
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]
        log_level = logging.WARNING

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging
    # Redirect standard library loggers (uvicorn, sqlalchemy, etc.)
    # through structlog so all logs share the same format
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Quiet noisy loggers in production
    if not debug:
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
