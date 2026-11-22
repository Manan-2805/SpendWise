from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import (
    EmailAlreadyRegisteredError,
    InvalidCredentialsError,
    UsernameAlreadyTakenError,
    UserNotFoundError,
)
from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import RegisterRequest
from app.schemas.user import UserResponse, UserUpdate
from app.services.user import UserService


@pytest.mark.asyncio
async def test_create_user_success() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()
    service.audit_service = MagicMock()

    service.repo.get_by_email = AsyncMock(return_value=None)
    service.repo.get_by_username = AsyncMock(return_value=None)
    mock_user = User(
        id=1,
        email="test@test.com",
        username="test",
        hashed_password="hashed_pass",
        is_active=True,
        is_verified=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.repo.create = AsyncMock(return_value=mock_user)
    service.audit_service.log_action = AsyncMock()

    data = RegisterRequest(
        email="test@test.com",
        username="test",
        password="Password123!",
        confirm_password="Password123!",
    )
    user = await service.create_user(data)

    assert user.id == 1
    assert user.email == "test@test.com"
    service.repo.create.assert_called_once()
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_create_user_email_taken() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    service.repo.get_by_email = AsyncMock(
        return_value=User(id=1, email="test@test.com")
    )
    data = RegisterRequest(
        email="test@test.com",
        username="test",
        password="Password123!",
        confirm_password="Password123!",
    )

    with pytest.raises(EmailAlreadyRegisteredError):
        await service.create_user(data)


@pytest.mark.asyncio
async def test_create_user_username_taken() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    service.repo.get_by_email = AsyncMock(return_value=None)
    service.repo.get_by_username = AsyncMock(return_value=User(id=1, username="test"))
    data = RegisterRequest(
        email="test@test.com",
        username="test",
        password="Password123!",
        confirm_password="Password123!",
    )

    with pytest.raises(UsernameAlreadyTakenError):
        await service.create_user(data)


@pytest.mark.asyncio
async def test_create_endpoint() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()
    service.audit_service = MagicMock()

    service.repo.get_by_email = AsyncMock(return_value=None)
    service.repo.get_by_username = AsyncMock(return_value=None)
    mock_user = User(
        id=1,
        email="test@test.com",
        username="test",
        hashed_password="hashed_pass",
        is_active=True,
        is_verified=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.repo.create = AsyncMock(return_value=mock_user)
    service.audit_service.log_action = AsyncMock()

    data = RegisterRequest(
        email="test@test.com",
        username="test",
        password="Password123!",
        confirm_password="Password123!",
    )
    res = await service.create(data)

    assert res.id == 1
    assert isinstance(res, UserResponse)


@pytest.mark.asyncio
async def test_get_by_id_success() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    mock_user = User(
        id=1,
        email="test@test.com",
        username="test",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.repo.get_by_id = AsyncMock(return_value=mock_user)

    res = await service.get_by_id(1)
    assert res.id == 1
    assert res.email == "test@test.com"


@pytest.mark.asyncio
async def test_get_by_id_not_found() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(UserNotFoundError):
        await service.get_by_id(99)


@pytest.mark.asyncio
async def test_get_by_email_success() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    mock_user = User(
        id=1,
        email="test@test.com",
        username="test",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.repo.get_by_email = AsyncMock(return_value=mock_user)

    res = await service.get_by_email("test@test.com")
    assert res.id == 1
    assert res.email == "test@test.com"


@pytest.mark.asyncio
async def test_get_by_email_not_found() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    service.repo.get_by_email = AsyncMock(return_value=None)
    with pytest.raises(UserNotFoundError):
        await service.get_by_email("wrong@test.com")


@pytest.mark.asyncio
async def test_update_user_success() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()
    service.audit_service = MagicMock()

    service.repo.get_by_email = AsyncMock(return_value=None)
    service.repo.get_by_username = AsyncMock(return_value=None)
    mock_user = User(
        id=1,
        email="new@test.com",
        username="newname",
        is_active=True,
        is_verified=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.repo.get_by_id = AsyncMock(return_value=mock_user)
    service.repo.update = AsyncMock(return_value=mock_user)
    service.audit_service.log_action = AsyncMock()

    update_data = UserUpdate(email="new@test.com", username="newname")
    res = await service.update(1, update_data)
    assert res.email == "new@test.com"
    assert res.username == "newname"
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_update_user_email_taken() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    service.repo.get_by_email = AsyncMock(
        return_value=User(id=2, email="taken@test.com")
    )
    update_data = UserUpdate(email="taken@test.com")
    with pytest.raises(EmailAlreadyRegisteredError):
        await service.update(1, update_data)


@pytest.mark.asyncio
async def test_update_user_username_taken() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    service.repo.get_by_email = AsyncMock(return_value=None)
    service.repo.get_by_username = AsyncMock(
        return_value=User(id=2, username="takenname")
    )
    update_data = UserUpdate(username="takenname")
    with pytest.raises(UsernameAlreadyTakenError):
        await service.update(1, update_data)


@pytest.mark.asyncio
async def test_update_user_not_found() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    service.repo.get_by_email = AsyncMock(return_value=None)
    service.repo.get_by_username = AsyncMock(return_value=None)
    service.repo.update = AsyncMock(return_value=None)

    update_data = UserUpdate(username="newname")
    with pytest.raises(UserNotFoundError):
        await service.update(99, update_data)


@pytest.mark.asyncio
async def test_soft_delete_success() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()
    service.audit_service = MagicMock()

    service.repo.soft_delete = AsyncMock(return_value=True)
    service.audit_service.log_action = AsyncMock()

    await service.soft_delete(1)
    service.repo.soft_delete.assert_called_once_with(1)
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_soft_delete_not_found() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    service.repo.soft_delete = AsyncMock(return_value=False)
    with pytest.raises(UserNotFoundError):
        await service.soft_delete(99)


@pytest.mark.asyncio
async def test_change_password_success() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()
    service.audit_service = MagicMock()

    hashed_old = hash_password("OldPassword123!")
    mock_user = User(
        id=1,
        hashed_password=hashed_old,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.repo.get_by_id = AsyncMock(return_value=mock_user)
    service.repo.update = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    await service.change_password(1, "OldPassword123!", "NewPassword123!")
    service.repo.update.assert_called_once()
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_change_password_invalid() -> None:
    db = MagicMock()
    service = UserService(db)
    service.repo = MagicMock()

    hashed_old = hash_password("OldPassword123!")
    mock_user = User(
        id=1,
        hashed_password=hashed_old,
        is_active=True,
        is_verified=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    service.repo.get_by_id = AsyncMock(return_value=mock_user)

    with pytest.raises(InvalidCredentialsError):
        await service.change_password(1, "WrongPassword!", "NewPassword123!")
