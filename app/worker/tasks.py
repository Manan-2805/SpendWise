import asyncio
from collections.abc import Coroutine, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from typing import Any

import structlog

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.audit import AuditLog
from app.models.user import User
from app.worker.celery_app import celery_app

logger = structlog.get_logger()


def _run_async(coro: Coroutine[Any, Any, Any]) -> None:
    """Run an async coroutine, supporting running loops in testing environments."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        with ThreadPoolExecutor(max_workers=1) as executor:
            executor.submit(asyncio.run, coro).result()
    else:
        asyncio.run(coro)


@celery_app.task
def send_verification_email(user_id: int, _: str | None = None) -> None:
    """Send an email verification link to a registered user."""

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            user: User | None = await session.get(User, user_id)
            if not user:
                logger.error("send_verification_email_user_not_found", user_id=user_id)
                return
            verification_url: str = (
                f"{settings.FRONTEND_URL}/verify-email?token={user.verification_token}"
            )
            logger.info(
                "verification_email_sent", email=user.email, url=verification_url
            )

    _run_async(_run())


@celery_app.task
def send_password_reset_email(
    user_id: int, reset_token: str, _: str | None = None
) -> None:
    """Send a password reset link to the user."""

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            user: User | None = await session.get(User, user_id)
            if not user:
                logger.error(
                    "send_password_reset_email_user_not_found", user_id=user_id
                )
                return
            reset_url: str = (
                f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
            )
            logger.info("password_reset_email_sent", email=user.email, url=reset_url)

    _run_async(_run())


@celery_app.task
def generate_monthly_report(
    user_id: int, year: int, month: int, _: str | None = None
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

            await service.category_breakdown(user_id, start_date, end_date)
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
def export_audit_logs(user_id: int, _: str | None = None) -> None:
    """Export user audit logs into CSV."""

    async def _run() -> None:
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

    _run_async(_run())


@celery_app.task
def generate_monthly_reports_for_all_users(correlation_id: str | None = None) -> None:
    """Queue monthly reports for all active users."""

    async def _run() -> None:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import select

            stmt = select(User.id).where(User.is_active, User.deleted_at.is_(None))
            result = await session.execute(stmt)
            user_ids: Sequence[int] = result.scalars().all()

            for uid in user_ids:
                generate_monthly_report.delay(
                    uid,
                    datetime.now().year,
                    datetime.now().month,
                    correlation_id=correlation_id,
                )
            logger.info("queued_monthly_reports_for_all_users", count=len(user_ids))

    _run_async(_run())
