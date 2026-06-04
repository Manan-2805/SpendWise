from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AccessDeniedError, CategoryNotFoundError, ConflictError
from app.models.category import Category
from app.schemas.category import CategoryCreate, CategoryUpdate
from app.services.category import CategoryService


@pytest.mark.asyncio
async def test_get_all_for_user() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    mock_cats = [
        Category(
            id=1,
            user_id=1,
            name="Rent",
            type="expense",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
        Category(
            id=2,
            user_id=1,
            name="Food",
            type="expense",
            created_at=datetime.now(),
            updated_at=datetime.now(),
        ),
    ]
    service.repo.get_by_user_id = AsyncMock(return_value=mock_cats)

    res = await service.get_all_for_user(1)
    assert len(res) == 2
    assert res[0].name == "Rent"


@pytest.mark.asyncio
async def test_get_by_id_success() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    mock_cat = Category(
        id=1,
        user_id=1,
        name="Rent",
        type="expense",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    service.repo.get_by_id = AsyncMock(return_value=mock_cat)

    res = await service.get_by_id(1, 1)
    assert res.id == 1


@pytest.mark.asyncio
async def test_get_by_id_not_found() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(CategoryNotFoundError):
        await service.get_by_id(99, 1)


@pytest.mark.asyncio
async def test_create_category_success() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()
    service.audit_service = MagicMock()

    service.repo.get_by_name_for_user = AsyncMock(return_value=None)
    mock_cat = Category(
        id=1,
        user_id=1,
        name="Utilities",
        description="Bills",
        icon="bolt",
        color="#000000",
        type="expense",
        created_at=datetime(2026, 6, 3, 12, 0, 0),
        updated_at=datetime(2026, 6, 3, 12, 0, 0),
    )
    service.repo.create = AsyncMock(return_value=mock_cat)
    service.audit_service.log_action = AsyncMock()

    data = CategoryCreate(
        name="Utilities",
        description="Bills",
        icon="bolt",
        color="#000000",
        type="expense",
    )
    res = await service.create(data, user_id=1)

    assert res.name == "Utilities"
    service.repo.get_by_name_for_user.assert_called_once_with("Utilities", 1)
    service.repo.create.assert_called_once()
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_create_category_duplicate() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    service.repo.get_by_name_for_user = AsyncMock(
        return_value=Category(id=1, name="Utilities")
    )

    data = CategoryCreate(
        name="Utilities",
        description="Bills",
        icon="bolt",
        color="#000000",
        type="expense",
    )
    with pytest.raises(ConflictError):
        await service.create(data, user_id=1)


@pytest.mark.asyncio
async def test_get_by_id_access_denied() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(
        return_value=Category(id=1, user_id=2, is_system=False)
    )

    with pytest.raises(AccessDeniedError):
        await service.get_by_id(category_id=1, user_id=1)


@pytest.mark.asyncio
async def test_update_category_success() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()
    service.audit_service = MagicMock()

    mock_cat = Category(
        id=1,
        user_id=1,
        name="Rent",
        type="expense",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    updated_cat = Category(
        id=1,
        user_id=1,
        name="New Rent",
        type="expense",
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    service.repo.get_by_id = AsyncMock(return_value=mock_cat)
    service.repo.get_by_name_for_user = AsyncMock(return_value=None)
    service.repo.update = AsyncMock(return_value=updated_cat)
    service.audit_service.log_action = AsyncMock()

    update_data = CategoryUpdate(name="New Rent", color="#FF0000")
    res = await service.update(1, update_data, 1)
    assert res.name == "New Rent"
    service.repo.update.assert_called_once()


@pytest.mark.asyncio
async def test_update_category_not_found() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(CategoryNotFoundError):
        await service.update(99, CategoryUpdate(name="New"), 1)


@pytest.mark.asyncio
async def test_update_category_access_denied() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(return_value=Category(id=1, user_id=2))
    with pytest.raises(AccessDeniedError):
        await service.update(1, CategoryUpdate(name="New"), 1)


@pytest.mark.asyncio
async def test_update_category_duplicate() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    mock_cat = Category(id=1, user_id=1, name="Rent")
    service.repo.get_by_id = AsyncMock(return_value=mock_cat)
    service.repo.get_by_name_for_user = AsyncMock(
        return_value=Category(id=2, name="Food")
    )

    with pytest.raises(ConflictError):
        await service.update(1, CategoryUpdate(name="Food"), 1)


@pytest.mark.asyncio
async def test_delete_category_not_found() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(CategoryNotFoundError):
        await service.soft_delete(99, 1)


@pytest.mark.asyncio
async def test_delete_category_access_denied() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(return_value=Category(id=1, user_id=2))
    with pytest.raises(AccessDeniedError):
        await service.soft_delete(1, 1)


@pytest.mark.asyncio
async def test_delete_category_with_active_transactions_no_reassign() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(return_value=Category(id=1, user_id=1))
    service.repo.has_active_transactions = AsyncMock(return_value=True)

    with pytest.raises(ConflictError):
        await service.soft_delete(category_id=1, user_id=1)


@pytest.mark.asyncio
async def test_delete_category_with_reassign() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()
    service.audit_service = MagicMock()

    service.repo.get_by_id = AsyncMock(
        side_effect=lambda cid: Category(id=cid, user_id=1) if cid in (1, 2) else None
    )
    service.repo.has_active_transactions = AsyncMock(return_value=True)
    service.repo.reassign_transactions = AsyncMock()
    service.repo.soft_delete = AsyncMock(return_value=True)
    service.audit_service.log_action = AsyncMock()

    await service.soft_delete(category_id=1, user_id=1, reassign_to_id=2)

    service.repo.reassign_transactions.assert_called_once_with(1, 2)
    service.repo.soft_delete.assert_called_once_with(1)
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_delete_category_reassign_target_not_found() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(
        side_effect=lambda cid: Category(id=cid, user_id=1) if cid == 1 else None
    )
    service.repo.has_active_transactions = AsyncMock(return_value=True)

    with pytest.raises(CategoryNotFoundError):
        await service.soft_delete(category_id=1, user_id=1, reassign_to_id=99)


@pytest.mark.asyncio
async def test_delete_category_reassign_target_access_denied() -> None:
    db = MagicMock()
    service = CategoryService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(
        side_effect=lambda cid: (
            Category(id=1, user_id=1)
            if cid == 1
            else Category(id=2, user_id=2, is_system=False)
        )
    )
    service.repo.has_active_transactions = AsyncMock(return_value=True)

    with pytest.raises(AccessDeniedError):
        await service.soft_delete(category_id=1, user_id=1, reassign_to_id=2)
