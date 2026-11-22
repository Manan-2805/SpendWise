import asyncio
import smtplib
import ssl
from collections.abc import Coroutine, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import UTC, date, datetime, timedelta
from email.message import EmailMessage
from threading import local
from typing import Any
from urllib.parse import urlencode

import structlog
from celery.signals import worker_process_shutdown

from app.core.config import settings
from app.core.redis import close_redis
from app.core.security import hash_refresh_token
from app.db.session import AsyncSessionLocal, engine
from app.models.audit import AuditLog
from app.models.user import User
from app.worker.celery_app import celery_app

logger = structlog.get_logger()


_worker_loop = local()


def _run_async[Result](coro: Coroutine[Any, Any, Result]) -> Result:
    """Reuse one event loop for pooled database and Redis clients in the worker."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        runner = getattr(_worker_loop, "runner", None)
        if runner is None:
            runner = _worker_loop.runner = asyncio.Runner()
        return runner.run(coro, context=copy_context())

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(copy_context().run, asyncio.run, coro).result()


@worker_process_shutdown.connect
def close_worker_resources(**_kwargs: Any) -> None:
    runner = getattr(_worker_loop, "runner", None)
    if runner is None:
        return

    async def close() -> None:
        await close_redis()
        await engine.dispose()

    runner.run(close())
    runner.close()
    del _worker_loop.runner


class EmailDeliveryError(Exception):
    pass


def _send_email(recipient: str, subject: str, path: str, token: str) -> None:
    if not settings.SMTP_HOST or not settings.SMTP_FROM:
        logger.warning("email_delivery_disabled", email_type=path)
        return
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM
    message["To"] = recipient
    message["Subject"] = subject
    query = urlencode({"token": token})
    message.set_content(f"{settings.FRONTEND_URL.rstrip('/')}/{path}?{query}")
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as client:
            if settings.SMTP_STARTTLS:
                client.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME:
                client.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            client.send_message(message)
    except (OSError, smtplib.SMTPException):
        raise EmailDeliveryError("SMTP delivery failed") from None
    logger.info("email_delivered", email_type=path)


def _deliver_account_email(user_id: int, token: str, *, verification: bool) -> None:
    async def deliver() -> None:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if user is None or user.deleted_at is not None or not user.is_active:
                return
            email = user.email
            digest, expires_at = (
                (user.verification_token, user.verification_token_expires_at)
                if verification
                else (user.reset_password_token, user.reset_token_expires_at)
            )
        if (
            digest != hash_refresh_token(token)
            or not expires_at
            or expires_at <= datetime.now(UTC)
        ):
            return
        subject, path = (
            ("Verify your SpendWise email", "verify-email")
            if verification
            else ("Reset your SpendWise password", "reset-password")
        )
        await asyncio.to_thread(_send_email, email, subject, path, token)

    _run_async(deliver())


@celery_app.task(
    autoretry_for=(EmailDeliveryError,),
    retry_backoff=True,
    max_retries=3,
    ignore_result=True,
)
def send_verification_email(
    user_id: int,
    token: str,
    correlation_id: str | None = None,  # noqa: ARG001
) -> None:
    _deliver_account_email(user_id, token, verification=True)


@celery_app.task(
    autoretry_for=(EmailDeliveryError,),
    retry_backoff=True,
    max_retries=3,
    ignore_result=True,
)
def send_password_reset_email(
    user_id: int,
    reset_token: str,
    correlation_id: str | None = None,  # noqa: ARG001
) -> None:
    _deliver_account_email(user_id, reset_token, verification=False)


@celery_app.task
def generate_monthly_report(
    user_id: int,
    year: int,
    month: int,
    correlation_id: str | None = None,  # noqa: ARG001
) -> None:
    """Generate and cache the monthly report for a user."""

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            from app.services.report import ReportService

            service = ReportService(session)
            await service.monthly_summary(user_id, year, month)

            start_date = date(year, month, 1)
            end_date: date = (
                date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            )

            await service.category_breakdown(
                user_id, start_date, end_date - timedelta(days=1)
            )
            logger.info(
                "monthly_report_generated", user_id=user_id, year=year, month=month
            )

    _run_async(_run())


@celery_app.task
def cleanup_expired_tokens(_: str | None = None) -> None:
    """Periodic task to purge expired refresh tokens from the database."""

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            from app.repositories.auth import AuthRepository

            repo = AuthRepository(session)
            count: int = await repo.cleanup_expired()
            await session.commit()
            logger.info("expired_tokens_cleaned", count=count)

    _run_async(_run())


@celery_app.task
def export_audit_logs(user_id: int, _: str | None = None) -> str:
    """Export user audit logs into CSV."""

    async def _run() -> str:
        async with AsyncSessionLocal() as session:
            from app.repositories.audit import AuditRepository

            repo = AuditRepository(session)
            logs: list[AuditLog] = await repo.get_for_user(user_id)

            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(
                ["id", "action", "resource_type", "resource_id", "created_at"]
            )
            for log in logs:
                writer.writerow(
                    [
                        log.id,
                        log.action,
                        log.resource_type,
                        log.resource_id,
                        log.created_at,
                    ]
                )

            logger.info("audit_logs_exported", user_id=user_id, length=len(logs))
            return output.getvalue()

    return _run_async(_run())


@celery_app.task
def generate_monthly_reports_for_all_users(correlation_id: str | None = None) -> None:
    """Queue monthly reports for all active users."""

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            stmt = select(User.id).where(User.is_active, User.deleted_at.is_(None))
            result = await session.execute(stmt)
            user_ids: Sequence[int] = result.scalars().all()

            month = datetime.now(UTC).date().replace(day=1) - timedelta(days=1)
            for uid in user_ids:
                generate_monthly_report.delay(
                    uid,
                    month.year,
                    month.month,
                    correlation_id=correlation_id,
                )
            logger.info("queued_monthly_reports_for_all_users", count=len(user_ids))

    _run_async(_run())
