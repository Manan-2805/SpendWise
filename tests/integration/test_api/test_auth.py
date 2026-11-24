import asyncio
from datetime import UTC, datetime, timedelta
from threading import Event
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.deps import get_db
from app.core.config import settings
from app.core.security import hash_password, hash_refresh_token, verify_token
from app.main import app
from app.models.auth import RefreshToken
from app.models.user import User
from tests.conftest import TestAsyncSessionLocal


@pytest.mark.parametrize("change", ["missing", "password", "inactive"])
async def test_login_releases_checkout_during_hashing(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    identity = uuid4().hex
    email = f"{identity}@example.com"
    if change != "missing":
        async with TestAsyncSessionLocal.begin() as seed:
            seed.add(
                User(
                    email=email,
                    username=identity,
                    hashed_password="fixture",
                    is_active=True,
                )
            )

    request_engine = create_async_engine(
        settings.ASYNC_DATABASE_URL, pool_size=1, max_overflow=0, pool_timeout=0.1
    )
    monkeypatch.delitem(app.dependency_overrides, get_db)
    monkeypatch.setattr(
        "app.api.deps.AsyncSessionLocal", async_sessionmaker(request_engine)
    )
    audit = AsyncMock()
    monkeypatch.setattr("app.services.auth.AuditService.log_action", audit)
    loop = asyncio.get_running_loop()
    started = asyncio.Event()
    released = Event()

    def pending_hash(*_args: str) -> bool:
        loop.call_soon_threadsafe(started.set)
        return released.wait(timeout=3)

    monkeypatch.setattr("app.services.auth.verify_password", pending_hash)
    payload = {"email": email, "password": "Password123!"}
    login = asyncio.create_task(client.post("/api/v1/auth/login", json=payload))
    try:
        await asyncio.wait_for(started.wait(), timeout=2)
        assert request_engine.sync_engine.pool.checkedout() == 0
        extra = await client.post("/api/v1/auth/login", json=payload)
        assert (extra.status_code, extra.headers.get("retry-after")) == (503, "1")

        if change != "missing":
            values = (
                {"is_active": False}
                if change == "inactive"
                else {"hashed_password": "changed"}
            )
            async with TestAsyncSessionLocal.begin() as writer:
                await writer.execute(
                    update(User).where(User.email == email).values(**values)
                )
        released.set()
        assert (await login).status_code == 401
        if change == "missing":
            assert audit.await_args.kwargs["action"] == "LOGIN_FAILED"
    finally:
        released.set()
        await asyncio.gather(login, return_exceptions=True)
        await request_engine.dispose()


async def test_register_success(client: AsyncClient, db_session: AsyncSession) -> None:
    payload = {
        "email": "test_register@example.com",
        "username": "test_register",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

    # Verify cookies
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies

    # Verify user exists in DB
    result = await db_session.execute(
        select(User).where(User.email == "test_register@example.com")
    )
    user = result.scalar_one_or_none()
    assert user is not None
    assert user.username == "test_register"


@pytest.mark.usefixtures("db_session")
async def test_register_duplicate_email(client: AsyncClient) -> None:
    # First user
    payload = {
        "email": "test_duplicate@example.com",
        "username": "test_dup1",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    response1 = await client.post("/api/v1/auth/register", json=payload)
    assert response1.status_code == 201

    # Duplicate registration
    payload["username"] = "test_dup2"
    response2 = await client.post("/api/v1/auth/register", json=payload)
    assert response2.status_code == 409
    assert response2.json()["code"] == "EMAIL_ALREADY_REGISTERED"


async def test_login_success(client: AsyncClient, db_session: AsyncSession) -> None:
    # Create a user directly in database
    hashed = hash_password("Password123!")
    user = User(
        email="test_login@example.com",
        username="test_login",
        hashed_password=hashed,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    payload = {"email": "test_login@example.com", "password": "Password123!"}
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies


async def test_login_invalid_password(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    hashed = hash_password("Password123!")
    user = User(
        email="test_login_fail@example.com",
        username="test_login_fail",
        hashed_password=hashed,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()

    payload = {"email": "test_login_fail@example.com", "password": "WrongPassword!"}
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["code"] == "INVALID_CREDENTIALS"


@pytest.mark.usefixtures("db_session")
async def test_refresh_token_success(client: AsyncClient) -> None:
    # Register to get initial cookies
    payload = {
        "email": "test_refresh@example.com",
        "username": "test_refresh",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    register_resp = await client.post("/api/v1/auth/register", json=payload)
    assert register_resp.status_code == 201

    refresh_token_cookie = client.cookies.get("refresh_token")
    assert refresh_token_cookie is not None

    # Call refresh endpoint (it automatically reads the cookie)
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 200

    data = response.json()
    assert "access_token" in data
    assert "access_token" in response.cookies
    assert "refresh_token" in response.cookies
    assert response.cookies.get("refresh_token") != refresh_token_cookie


async def test_refresh_token_reuse_revokes_family(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    # Register to get initial cookies
    payload = {
        "email": "test_reuse@example.com",
        "username": "test_reuse",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    register_resp = await client.post("/api/v1/auth/register", json=payload)
    assert register_resp.status_code == 201

    first_refresh_cookie = client.cookies.get("refresh_token")
    assert first_refresh_cookie is not None

    # Call refresh once
    response1 = await client.post("/api/v1/auth/refresh")
    assert response1.status_code == 200

    # Call refresh again with the OLD cookie (reuse!)
    client.cookies.set("refresh_token", first_refresh_cookie)
    response2 = await client.post("/api/v1/auth/refresh")
    assert response2.status_code == 401
    assert response2.json()["code"] == "INVALID_TOKEN"

    # Verify that all refresh tokens for this family/user are now revoked/deleted
    user_id = int(verify_token(first_refresh_cookie, "refresh")["sub"])
    result = await db_session.execute(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    )
    tokens = result.scalars().all()
    assert len(tokens) == 2
    # Any active token for this user should be gone or marked revoked
    for tok in tokens:
        assert tok.revoked_at is not None


@pytest.mark.usefixtures("db_session")
async def test_logout(client: AsyncClient) -> None:
    payload = {
        "email": "test_logout@example.com",
        "username": "test_logout",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    await client.post("/api/v1/auth/register", json=payload)

    # Logout
    response = await client.post("/api/v1/auth/logout")
    assert response.status_code == 200
    assert response.json() == {"message": "Successfully logged out"}

    # Cookies should be empty
    assert client.cookies.get("access_token") in (None, "")
    assert client.cookies.get("refresh_token") in (None, "")


@pytest.mark.usefixtures("db_session")
async def test_change_password(client: AsyncClient) -> None:
    payload = {
        "email": "test_changepass@example.com",
        "username": "test_changepass",
        "password": "Password123!",
        "confirm_password": "Password123!",
    }
    await client.post("/api/v1/auth/register", json=payload)

    # Change password
    change_payload = {
        "current_password": "Password123!",
        "new_password": "NewPassword123!",
        "confirm_new_password": "NewPassword123!",
    }
    response = await client.post("/api/v1/auth/change-password", json=change_payload)
    assert response.status_code == 200
    assert "Password changed successfully" in response.json()["message"]

    # Try login with new password
    login_payload = {
        "email": "test_changepass@example.com",
        "password": "NewPassword123!",
    }
    login_resp = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200


async def test_forgot_and_reset_password(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Create user
    hashed = hash_password("Password123!")
    user = User(
        email="test_reset@example.com",
        username="test_reset",
        hashed_password=hashed,
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()

    enqueue = MagicMock()
    monkeypatch.setattr(
        "app.worker.tasks.send_password_reset_email.apply_async", enqueue
    )
    # Request forgot password
    forgot_payload = {"email": "test_reset@example.com"}
    forgot_resp = await client.post("/api/v1/auth/forgot-password", json=forgot_payload)
    assert forgot_resp.status_code == 200

    # The broker receives the token and the database retains only its digest.
    await db_session.refresh(user)
    reset_token = enqueue.call_args.kwargs["args"][1]
    assert user.reset_password_token == hash_refresh_token(reset_token)

    # Reset password
    reset_payload = {
        "token": reset_token,
        "new_password": "NewPassword123!",
        "confirm_new_password": "NewPassword123!",
    }
    reset_resp = await client.post("/api/v1/auth/reset-password", json=reset_payload)
    assert reset_resp.status_code == 200

    # Login with new password
    login_payload = {
        "email": "test_reset@example.com",
        "password": "NewPassword123!",
    }
    login_resp = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200


async def test_verify_email(client: AsyncClient, db_session: AsyncSession) -> None:
    # Create unverified user
    hashed = hash_password("Password123!")
    user = User(
        email="test_verify@example.com",
        username="test_verify",
        hashed_password=hashed,
        is_active=True,
        is_verified=False,
        verification_token=hash_refresh_token("some_verification_token"),
        verification_token_expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    db_session.add(user)
    await db_session.flush()

    # Call verify-email
    response = await client.get(
        "/api/v1/auth/verify-email?token=some_verification_token"
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Email verified successfully."}

    # Check database
    await db_session.refresh(user)
    assert user.is_verified is True
    assert user.verification_token is None


async def test_verify_email_invalid_token(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/verify-email?token=invalid_token")
    assert response.status_code == 401


async def test_resend_verification_success(
    client: AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    send = MagicMock()
    monkeypatch.setattr("app.worker.tasks._send_email", send)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.test")
    monkeypatch.setattr(settings, "SMTP_FROM", "spendwise@example.test")
    # Create unverified user
    hashed = hash_password("Password123!")
    user = User(
        email="unverified_resend@example.com",
        username="unverified_resend",
        hashed_password=hashed,
        is_active=True,
        is_verified=False,
    )
    db_session.add(user)
    await db_session.commit()

    # Authenticate user first
    payload = {"email": "unverified_resend@example.com", "password": "Password123!"}
    login_resp = await client.post("/api/v1/auth/login", json=payload)
    assert login_resp.status_code == 200

    response = await client.post("/api/v1/auth/resend-verification")
    assert response.status_code == 200
    assert (
        response.json()["message"] == "Verification email accepted by the mail server."
    )
    assert send.call_args.args[0] == user.email


@pytest.mark.parametrize("smtp_configured", [False, True])
async def test_resend_verification_reports_email_failure(
    client: AsyncClient,
    test_user: User,
    auth_headers: callable,
    monkeypatch: pytest.MonkeyPatch,
    smtp_configured: bool,
) -> None:
    from app.worker.tasks import EmailDeliveryError

    monkeypatch.setattr(
        settings, "SMTP_HOST", "smtp.example.test" if smtp_configured else ""
    )
    monkeypatch.setattr(settings, "SMTP_FROM", "spendwise@example.test")
    send = MagicMock(side_effect=EmailDeliveryError("Relay rejected the message"))
    monkeypatch.setattr("app.worker.tasks._send_email", send)

    response = await client.post(
        "/api/v1/auth/resend-verification", headers=auth_headers(test_user)
    )

    assert response.status_code == 503
    assert response.json()["code"] == "SERVICE_UNAVAILABLE"
    assert send.call_count == int(smtp_configured)
