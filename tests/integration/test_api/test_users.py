from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_password
from app.models.user import User


async def test_get_me_success(
    client: AsyncClient, verified_user: User, auth_headers: callable
) -> None:
    headers = auth_headers(verified_user)
    response = await client.get("/api/v1/users/me", headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["email"] == verified_user.email
    assert data["username"] == verified_user.username


async def test_get_me_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/me")
    assert response.status_code == 401


async def test_update_me_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    payload = {"username": "new_awesome_username"}
    response = await client.patch("/api/v1/users/me", json=payload, headers=headers)
    assert response.status_code == 200

    data = response.json()
    assert data["username"] == "new_awesome_username"

    # Verify database update
    await db_session.refresh(verified_user)
    assert verified_user.username == "new_awesome_username"


async def test_change_password_me_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    # verified_user has default password hashed from UserFactory: "TestPassword123!"
    payload = {
        "current_password": "TestPassword123!",
        "new_password": "NewPasswordXYZ123!",
        "confirm_new_password": "NewPasswordXYZ123!",
    }
    response = await client.post(
        "/api/v1/users/me/password", json=payload, headers=headers
    )
    assert response.status_code == 200
    assert response.json() == {"message": "Password changed successfully"}

    # Verify password hash in DB
    await db_session.refresh(verified_user)
    assert verify_password("NewPasswordXYZ123!", verified_user.hashed_password) is True


async def test_delete_me_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    response = await client.delete("/api/v1/users/me", headers=headers)
    assert response.status_code == 204

    # Verify soft delete in DB
    await db_session.refresh(verified_user)
    assert verified_user.deleted_at is not None
    assert verified_user.is_deleted is True
