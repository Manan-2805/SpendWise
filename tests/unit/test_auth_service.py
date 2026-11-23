import asyncio
from datetime import UTC, datetime, timedelta
from threading import Event
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    OverloadedError,
)
from app.core.security import hash_password
from app.db.session import run_after_commit
from app.models.auth import RefreshToken
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.services.auth import AuthService


async def test_cancelled_login_keeps_bcrypt_slot_until_thread_exits(
    monkeypatch,
) -> None:
    from app.services import auth

    slot = asyncio.Semaphore(1)
    monkeypatch.setattr(auth, "_login_slots", slot)
    started = asyncio.Event()
    released = Event()
    loop = asyncio.get_running_loop()

    def block(*_args: str) -> bool:
        loop.call_soon_threadsafe(started.set)
        return released.wait(timeout=3)

    monkeypatch.setattr(auth, "verify_password", block)
    task = asyncio.create_task(auth.verify_login_password("pw", "hash"))
    try:
        await asyncio.wait_for(started.wait(), timeout=1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(OverloadedError):
            await auth.verify_login_password("pw", "hash")
    finally:
        released.set()
        await asyncio.wait_for(slot.acquire(), timeout=1)
        slot.release()
    assert await auth.verify_login_password("pw", "hash")


@pytest.mark.asyncio
async def test_register_delegates_to_user_service() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()

    mock_user = User(id=1, email="test@test.com", username="test")
    service.user_service.create_user = AsyncMock(return_value=mock_user)

    data = RegisterRequest(
        email="test@test.com",
        username="test",
        password="Password123!",
        confirm_password="Password123!",
    )
    user = await service.register(data)

    assert user.id == 1
    service.user_service.create_user.assert_called_once_with(data)


@pytest.mark.asyncio
async def test_authenticate_success() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )
    service.audit_service = MagicMock()

    hashed = hash_password("Password123!")
    mock_user = User(
        id=1,
        email="test@test.com",
        username="test",
        hashed_password=hashed,
        is_active=True,
    )
    service.user_service.repo.get_by_email = AsyncMock(return_value=mock_user)
    service.auth_repo.lock_active_user.return_value = mock_user
    service.auth_repo.create_refresh_token = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    import app.services.auth as auth_mod

    original_verify = auth_mod.verify_token
    auth_mod.verify_token = MagicMock(
        return_value={"sub": 1, "jti": "jti1", "exp": 9999999999, "type": "refresh"}
    )

    try:
        access_token, refresh_token, user = await service.authenticate(
            "test@test.com", "Password123!"
        )
        assert user.id == 1
        assert access_token is not None
        assert refresh_token is not None
        service.auth_repo.create_refresh_token.assert_called_once()
        service.audit_service.log_action.assert_called_once_with(
            action="LOGIN_SUCCESS",
            resource_type="User",
            resource_id=1,
            user_id=1,
        )
    finally:
        auth_mod.verify_token = original_verify


@pytest.mark.asyncio
async def test_authenticate_invalid_credentials() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()
    service.audit_service = MagicMock()

    service.user_service.repo.get_by_email = AsyncMock(return_value=None)
    service.audit_service.log_action = AsyncMock()

    with pytest.raises(InvalidCredentialsError):
        await service.authenticate("wrong@test.com", "any_password")

    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_authenticate_inactive_user() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()
    service.audit_service = MagicMock()

    hashed = hash_password("Password123!")
    mock_user = User(
        id=1,
        email="test@test.com",
        username="test",
        hashed_password=hashed,
        is_active=False,
    )
    service.user_service.repo.get_by_email = AsyncMock(return_value=mock_user)
    service.audit_service.log_action = AsyncMock()

    with pytest.raises(InactiveUserError):
        await service.authenticate("test@test.com", "Password123!")


@pytest.mark.asyncio
async def test_refresh_tokens_success() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )
    service.audit_service = MagicMock()

    import app.services.auth as auth_mod

    original_verify = auth_mod.verify_token
    auth_mod.verify_token = MagicMock(
        return_value={"sub": 1, "jti": "jti1", "exp": 9999999999, "type": "refresh"}
    )

    db_token = RefreshToken(
        id=1,
        user_id=1,
        jti="jti1",
        family_id="fam1",
        revoked_at=None,
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    service.auth_repo.get_by_hash = AsyncMock(return_value=db_token)
    service.auth_repo.revoke_token = AsyncMock()
    service.auth_repo.create_refresh_token = AsyncMock()

    try:
        new_access, new_refresh = await service.refresh_tokens("raw_token_here")
        assert new_access is not None
        assert new_refresh is not None
        service.auth_repo.revoke_token.assert_called_once_with("jti1")
        service.auth_repo.create_refresh_token.assert_called_once()
    finally:
        auth_mod.verify_token = original_verify


@pytest.mark.asyncio
async def test_refresh_token_reuse_detected() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )
    service.audit_service = MagicMock()

    import app.services.auth as auth_mod

    original_verify = auth_mod.verify_token
    auth_mod.verify_token = MagicMock(
        return_value={"sub": 1, "jti": "jti1", "exp": 9999999999, "type": "refresh"}
    )

    db_token = RefreshToken(
        id=1,
        user_id=1,
        jti="jti1",
        family_id="fam1",
        revoked_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    service.auth_repo.get_by_hash = AsyncMock(return_value=db_token)
    service.auth_repo.revoke_family = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    try:
        with pytest.raises(InvalidTokenError):
            await service.refresh_tokens("raw_token_here")

        service.auth_repo.revoke_family.assert_called_once_with("fam1")
        service.audit_service.log_action.assert_called_once()
    finally:
        auth_mod.verify_token = original_verify


@pytest.mark.asyncio
async def test_refresh_tokens_expired() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )

    import app.services.auth as auth_mod

    original_verify = auth_mod.verify_token
    auth_mod.verify_token = MagicMock(
        return_value={"sub": 1, "jti": "jti1", "exp": 100, "type": "refresh"}
    )

    db_token = RefreshToken(
        id=1,
        user_id=1,
        jti="jti1",
        family_id="fam1",
        revoked_at=None,
        expires_at=datetime.now(UTC) - timedelta(days=1),
    )
    service.auth_repo.get_by_hash = AsyncMock(return_value=db_token)

    try:
        with pytest.raises(InvalidTokenError):
            await service.refresh_tokens("raw_token")
    finally:
        auth_mod.verify_token = original_verify


@pytest.mark.asyncio
async def test_refresh_tokens_not_found() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )

    import app.services.auth as auth_mod

    original_verify = auth_mod.verify_token
    auth_mod.verify_token = MagicMock(
        return_value={"sub": 1, "jti": "jti1", "exp": 9999999999, "type": "refresh"}
    )
    service.auth_repo.get_by_hash = AsyncMock(return_value=None)

    try:
        with pytest.raises(InvalidTokenError):
            await service.refresh_tokens("raw_token")
    finally:
        auth_mod.verify_token = original_verify


@pytest.mark.asyncio
async def test_refresh_tokens_decode_error() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)

    import app.services.auth as auth_mod

    original_verify = auth_mod.verify_token
    auth_mod.verify_token = MagicMock(side_effect=Exception)

    try:
        with pytest.raises(InvalidTokenError):
            await service.refresh_tokens("bad_token")
    finally:
        auth_mod.verify_token = original_verify


@pytest.mark.asyncio
async def test_revoke_user_tokens() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )
    service.audit_service = MagicMock()

    service.auth_repo.invalidate_sessions = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    await service.revoke_user_tokens(1)
    service.auth_repo.invalidate_sessions.assert_called_once_with(1)
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_change_password() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )

    service.user_service.change_password = AsyncMock()
    service.auth_repo.invalidate_sessions = AsyncMock()

    await service.change_password(1, "old", "new")
    service.user_service.change_password.assert_called_once_with(1, "old", "new")
    service.auth_repo.invalidate_sessions.assert_called_once_with(1)


@pytest.mark.asyncio
async def test_forgot_password_success() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()
    service.audit_service = MagicMock()

    mock_user = User(id=1, email="test@test.com")
    service.user_service.repo.get_by_email = AsyncMock(return_value=mock_user)
    service.user_service.repo.update = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    with patch(
        "app.worker.tasks.send_password_reset_email.apply_async"
    ) as mock_reset_task:
        await service.forgot_password("test@test.com")
        service.user_service.repo.update.assert_called_once()
        mock_reset_task.assert_not_called()
        await run_after_commit(db)
        mock_reset_task.assert_called_once()
        service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_forgot_password_not_found() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()

    service.user_service.repo.get_by_email = AsyncMock(return_value=None)
    await service.forgot_password("wrong@test.com")


@pytest.mark.asyncio
async def test_reset_password_success() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )
    service.audit_service = MagicMock()

    mock_user = User(
        id=1, reset_token_expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    service.user_service.repo.get_by_reset_token = AsyncMock(return_value=mock_user)
    service.user_service.repo.update = AsyncMock()
    service.auth_repo.invalidate_sessions = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    await service.reset_password("token", "new_password")
    service.user_service.repo.update.assert_called_once()
    service.auth_repo.invalidate_sessions.assert_called_once_with(1)
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_reset_password_not_found() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()

    service.user_service.repo.get_by_reset_token = AsyncMock(return_value=None)
    with pytest.raises(InvalidTokenError):
        await service.reset_password("token", "new")


@pytest.mark.asyncio
async def test_reset_password_expired() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()

    mock_user = User(
        id=1, reset_token_expires_at=datetime.now(UTC) - timedelta(hours=1)
    )
    service.user_service.repo.get_by_reset_token = AsyncMock(return_value=mock_user)
    with pytest.raises(InvalidTokenError):
        await service.reset_password("token", "new")


@pytest.mark.asyncio
async def test_verify_email_success() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()
    service.audit_service = MagicMock()

    mock_user = User(
        id=1, verification_token_expires_at=datetime.now(UTC) + timedelta(hours=1)
    )
    service.user_service.repo.get_by_verification_token = AsyncMock(
        return_value=mock_user
    )
    service.user_service.repo.update = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    await service.verify_email("token")
    service.user_service.repo.update.assert_called_once()
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_verify_email_not_found() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()

    service.user_service.repo.get_by_verification_token = AsyncMock(return_value=None)
    with pytest.raises(InvalidTokenError):
        await service.verify_email("token")


@pytest.mark.asyncio
async def test_resend_verification_unverified() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()

    mock_user = User(
        id=1, email="test@test.com", is_verified=False, verification_token="token"
    )
    service.user_service.repo.get_by_email = AsyncMock(return_value=mock_user)
    service.user_service.repo.update = AsyncMock()

    with patch(
        "app.worker.tasks.send_verification_email.apply_async"
    ) as mock_verify_task:
        await service.resend_verification("test@test.com")
        mock_verify_task.assert_not_called()
        await run_after_commit(db)
        mock_verify_task.assert_called_once()


@pytest.mark.asyncio
async def test_resend_verification_verified() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.user_service = MagicMock()

    mock_user = User(id=1, email="test@test.com", is_verified=True)
    service.user_service.repo.get_by_email = AsyncMock(return_value=mock_user)

    await service.resend_verification("test@test.com")


@pytest.mark.asyncio
async def test_login_or_register_oauth_success_link() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )
    service.user_service = MagicMock()
    service.audit_service = MagicMock()

    mock_user = User(id=1, is_active=True)
    mock_oauth = MagicMock(user_id=1)
    service.auth_repo.get_oauth_account = AsyncMock(return_value=mock_oauth)
    service.user_service.repo.get_by_id = AsyncMock(return_value=mock_user)
    service.auth_repo.create_refresh_token = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    import app.services.auth as auth_mod

    original_verify = auth_mod.verify_token
    auth_mod.verify_token = MagicMock(
        return_value={"sub": 1, "jti": "jti1", "exp": 9999999999, "type": "refresh"}
    )

    try:
        _, _, usr = await service.login_or_register_oauth(
            "google", "sub1", "test@test.com", "test"
        )
        assert usr.id == 1
    finally:
        auth_mod.verify_token = original_verify


@pytest.mark.asyncio
async def test_login_or_register_oauth_success_create() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )
    service.user_service = MagicMock()
    service.audit_service = MagicMock()

    service.auth_repo.get_oauth_account = AsyncMock(return_value=None)
    service.user_service.repo.get_by_email = AsyncMock(return_value=None)
    service.user_service.repo.get_by_username = AsyncMock(return_value=None)

    mock_user = User(id=1, is_active=True)
    service.user_service.repo.create = AsyncMock(return_value=mock_user)
    service.auth_repo.create_oauth_account = AsyncMock()
    service.auth_repo.create_refresh_token = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    import app.services.auth as auth_mod

    original_verify = auth_mod.verify_token
    auth_mod.verify_token = MagicMock(
        return_value={"sub": 1, "jti": "jti1", "exp": 9999999999, "type": "refresh"}
    )

    try:
        _, _, usr = await service.login_or_register_oauth(
            "google", "sub1", "test@test.com", "test"
        )
        assert usr.id == 1
    finally:
        auth_mod.verify_token = original_verify


@pytest.mark.asyncio
async def test_login_or_register_oauth_username_collision() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )
    service.user_service = MagicMock()
    service.audit_service = MagicMock()

    service.auth_repo.get_oauth_account = AsyncMock(return_value=None)
    service.user_service.repo.get_by_email = AsyncMock(return_value=None)
    service.user_service.repo.get_by_username = AsyncMock(
        return_value=User(id=2, username="test")
    )

    mock_user = User(id=1, is_active=True)
    service.user_service.repo.create = AsyncMock(return_value=mock_user)
    service.auth_repo.create_oauth_account = AsyncMock()
    service.auth_repo.create_refresh_token = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    import app.services.auth as auth_mod

    original_verify = auth_mod.verify_token
    auth_mod.verify_token = MagicMock(
        return_value={"sub": 1, "jti": "jti1", "exp": 9999999999, "type": "refresh"}
    )

    try:
        _, _, usr = await service.login_or_register_oauth(
            "google", "sub1", "test@test.com", "test"
        )
        assert usr.id == 1
        service.user_service.repo.create.assert_called_once()
    finally:
        auth_mod.verify_token = original_verify


@pytest.mark.asyncio
async def test_login_or_register_oauth_inactive() -> None:
    db = MagicMock(spec=AsyncSession)
    db.info = {}
    service = AuthService(db)
    service.auth_repo = MagicMock()
    service.auth_repo.lock_active_user = AsyncMock(
        return_value=User(id=1, is_active=True)
    )
    service.user_service = MagicMock()

    mock_user = User(id=1, is_active=False)
    mock_oauth = MagicMock(user_id=1)
    service.auth_repo.get_oauth_account = AsyncMock(return_value=mock_oauth)
    service.user_service.repo.get_by_id = AsyncMock(return_value=mock_user)

    with pytest.raises(InactiveUserError):
        await service.login_or_register_oauth("google", "sub1", "test@test.com", "test")
