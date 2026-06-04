import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.auth import RefreshToken
from app.models.user import User


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
    await db_session.flush()

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
    await db_session.flush()

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
    result = await db_session.execute(select(RefreshToken))
    tokens = result.scalars().all()
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
    client: AsyncClient, db_session: AsyncSession
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

    # Request forgot password
    forgot_payload = {"email": "test_reset@example.com"}
    forgot_resp = await client.post("/api/v1/auth/forgot-password", json=forgot_payload)
    assert forgot_resp.status_code == 200

    # Retrieve reset token from DB
    await db_session.refresh(user)
    reset_token = user.reset_password_token
    assert reset_token is not None

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
        verification_token="some_verification_token",
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
    client: AsyncClient, db_session: AsyncSession
) -> None:
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
    await db_session.flush()

    # Authenticate user first
    payload = {"email": "unverified_resend@example.com", "password": "Password123!"}
    login_resp = await client.post("/api/v1/auth/login", json=payload)
    assert login_resp.status_code == 200

    response = await client.post("/api/v1/auth/resend-verification")
    assert response.status_code == 200


async def test_google_login_disabled(client: AsyncClient) -> None:
    import app.api.v1.endpoints.auth as auth_module

    original = auth_module.settings.GOOGLE_OAUTH_ENABLED
    auth_module.settings.GOOGLE_OAUTH_ENABLED = False
    try:
        response = await client.get("/api/v1/auth/google")
        assert response.status_code == 400
    finally:
        auth_module.settings.GOOGLE_OAUTH_ENABLED = original


async def test_google_login_enabled(client: AsyncClient) -> None:
    from unittest.mock import AsyncMock, patch

    import app.api.v1.endpoints.auth as auth_module

    original = auth_module.settings.GOOGLE_OAUTH_ENABLED
    auth_module.settings.GOOGLE_OAUTH_ENABLED = True
    try:
        with patch.object(
            auth_module.oauth.google,
            "authorize_redirect",
            new=AsyncMock(return_value="redirected"),
        ):
            response = await client.get("/api/v1/auth/google")
            assert response.status_code == 200
            assert response.json() == "redirected"
    finally:
        auth_module.settings.GOOGLE_OAUTH_ENABLED = original


async def test_google_callback_disabled(client: AsyncClient) -> None:
    import app.api.v1.endpoints.auth as auth_module

    original = auth_module.settings.GOOGLE_OAUTH_ENABLED
    auth_module.settings.GOOGLE_OAUTH_ENABLED = False
    try:
        response = await client.get("/api/v1/auth/google/callback")
        assert response.status_code == 400
    finally:
        auth_module.settings.GOOGLE_OAUTH_ENABLED = original


async def test_google_callback_authorize_fail(client: AsyncClient) -> None:
    from unittest.mock import AsyncMock, patch

    import app.api.v1.endpoints.auth as auth_module

    original = auth_module.settings.GOOGLE_OAUTH_ENABLED
    auth_module.settings.GOOGLE_OAUTH_ENABLED = True
    try:
        with patch.object(
            auth_module.oauth.google,
            "authorize_access_token",
            new=AsyncMock(side_effect=Exception("Failed")),
        ):
            response = await client.get("/api/v1/auth/google/callback")
            assert response.status_code == 400
    finally:
        auth_module.settings.GOOGLE_OAUTH_ENABLED = original


async def test_google_callback_missing_userinfo(client: AsyncClient) -> None:
    from unittest.mock import AsyncMock, patch

    import app.api.v1.endpoints.auth as auth_module

    original = auth_module.settings.GOOGLE_OAUTH_ENABLED
    auth_module.settings.GOOGLE_OAUTH_ENABLED = True
    try:
        with patch.object(
            auth_module.oauth.google,
            "authorize_access_token",
            new=AsyncMock(return_value={}),
        ):
            response = await client.get("/api/v1/auth/google/callback")
            assert response.status_code == 400
    finally:
        auth_module.settings.GOOGLE_OAUTH_ENABLED = original


async def test_google_callback_success(client: AsyncClient) -> None:
    from unittest.mock import AsyncMock, patch

    import app.api.v1.endpoints.auth as auth_module

    mock_token = {
        "userinfo": {
            "email": "oauth@example.com",
            "name": "OAuth User",
            "sub": "google-sub-id",
        }
    }
    mock_user = User(id=1, email="oauth@example.com", username="oauth")
    original = auth_module.settings.GOOGLE_OAUTH_ENABLED
    auth_module.settings.GOOGLE_OAUTH_ENABLED = True
    try:
        with (
            patch.object(
                auth_module.oauth.google,
                "authorize_access_token",
                new=AsyncMock(return_value=mock_token),
            ),
            patch(
                "app.services.auth.AuthService.login_or_register_oauth",
                new=AsyncMock(return_value=("mock_access", "mock_refresh", mock_user)),
            ),
        ):
            response = await client.get("/api/v1/auth/google/callback")
            assert response.status_code == 200
            data = response.json()
            assert data["access_token"] == "mock_access"
            assert "access_token" in response.cookies
            assert "refresh_token" in response.cookies
    finally:
        auth_module.settings.GOOGLE_OAUTH_ENABLED = original
