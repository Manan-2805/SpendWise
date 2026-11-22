from typing import Any

import structlog
from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging, task_prerun

from app.core.config import settings
from app.core.logging import configure_logging

celery_app = Celery(
    "spendwise",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.worker.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    broker_connection_timeout=2,
    task_soft_time_limit=300,
    task_time_limit=600,
)

celery_app.conf.beat_schedule = {
    "cleanup-expired-tokens-every-hour": {
        "task": "app.worker.tasks.cleanup_expired_tokens",
        "schedule": 3600.0,
    },
    "generate-monthly-reports-for-all-users-monthly": {
        "task": "app.worker.tasks.generate_monthly_reports_for_all_users",
        "schedule": crontab(day_of_month="1", hour="0", minute="0"),
    },
}


@setup_logging.connect
def setup_worker_logging(**_kwargs: Any) -> None:
    configure_logging(debug=settings.DEBUG)


@task_prerun.connect
def task_prerun_handler(
    task_id: str, task: Any, kwargs: dict[str, Any], **_kw: Any
) -> None:
    """Inject correlation ID to task structured log context."""
    corr_id = kwargs.get("correlation_id") or getattr(
        task.request, "correlation_id", None
    )
    structlog.contextvars.clear_contextvars()
    if corr_id:
        structlog.contextvars.bind_contextvars(correlation_id=corr_id, task_id=task_id)
