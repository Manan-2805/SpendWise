from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User
from app.worker.tasks import (
    cleanup_expired_tokens,
    export_audit_logs,
    generate_monthly_report,
    generate_monthly_reports_for_all_users,
    send_password_reset_email,
    send_verification_email,
)


@pytest.mark.asyncio
async def test_send_verification_email_success() -> None:
    mock_session = AsyncMock()
    mock_user = User(id=1, email="test@test.com", verification_token="verify_token")
    mock_session.get.return_value = mock_user

    mock_session_local = MagicMock()
    # Async context manager mock
    mock_session_local.return_value.__aenter__.return_value = mock_session

    with patch("app.worker.tasks.AsyncSessionLocal", mock_session_local):
        send_verification_email(1)
        mock_session.get.assert_called_once_with(User, 1)


@pytest.mark.asyncio
async def test_send_verification_email_user_not_found() -> None:
    mock_session = AsyncMock()
    mock_session.get.return_value = None

    mock_session_local = MagicMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    with patch("app.worker.tasks.AsyncSessionLocal", mock_session_local):
        send_verification_email(99)
        mock_session.get.assert_called_once_with(User, 99)


@pytest.mark.asyncio
async def test_send_password_reset_email_success() -> None:
    mock_session = AsyncMock()
    mock_user = User(id=1, email="test@test.com")
    mock_session.get.return_value = mock_user

    mock_session_local = MagicMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    with patch("app.worker.tasks.AsyncSessionLocal", mock_session_local):
        send_password_reset_email(1, "reset_token")
        mock_session.get.assert_called_once_with(User, 1)


@pytest.mark.asyncio
async def test_generate_monthly_report() -> None:
    mock_session = AsyncMock()
    mock_session_local = MagicMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_service = MagicMock()
    mock_service.monthly_summary = AsyncMock()
    mock_service.category_breakdown = AsyncMock()

    with (
        patch("app.worker.tasks.AsyncSessionLocal", mock_session_local),
        patch("app.services.report.ReportService", return_value=mock_service),
    ):
        generate_monthly_report(1, 2026, 6)
        mock_service.monthly_summary.assert_called_once_with(1, 2026, 6)
        mock_service.category_breakdown.assert_called_once()


@pytest.mark.asyncio
async def test_cleanup_expired_tokens() -> None:
    mock_session = AsyncMock()
    mock_session_local = MagicMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_repo = MagicMock()
    mock_repo.cleanup_expired = AsyncMock(return_value=5)

    with (
        patch("app.worker.tasks.AsyncSessionLocal", mock_session_local),
        patch("app.repositories.auth.AuthRepository", return_value=mock_repo),
    ):
        cleanup_expired_tokens()
        mock_repo.cleanup_expired.assert_called_once()
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_export_audit_logs() -> None:
    mock_session = AsyncMock()
    mock_session_local = MagicMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_repo = MagicMock()
    mock_repo.get_for_user = AsyncMock(return_value=[])

    with (
        patch("app.worker.tasks.AsyncSessionLocal", mock_session_local),
        patch("app.repositories.audit.AuditRepository", return_value=mock_repo),
    ):
        export_audit_logs(1)
        mock_repo.get_for_user.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_generate_monthly_reports_for_all_users() -> None:
    mock_session = AsyncMock()
    mock_session_local = MagicMock()
    mock_session_local.return_value.__aenter__.return_value = mock_session

    mock_result = MagicMock()
    mock_result.scalars().all.return_value = [1, 2, 3]
    mock_session.execute = AsyncMock(return_value=mock_result)

    with (
        patch("app.worker.tasks.AsyncSessionLocal", mock_session_local),
        patch("app.worker.tasks.generate_monthly_report.delay") as mock_delay,
    ):
        generate_monthly_reports_for_all_users()
        assert mock_delay.call_count == 3
