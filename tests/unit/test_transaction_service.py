from datetime import date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccessDeniedError,
    CategoryNotFoundError,
    TransactionNotFoundError,
)
from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.transaction import (
    TransactionCreate,
    TransactionFilters,
    TransactionUpdate,
)
from app.services.transaction import TransactionService


@pytest.mark.asyncio
async def test_create_transaction_success() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()
    service.category_repo = MagicMock()
    service.audit_service = MagicMock()

    service.category_repo.get_by_id = AsyncMock(return_value=Category(id=1, user_id=1))
    mock_tx = Transaction(
        id=1,
        user_id=1,
        category_id=1,
        amount=Decimal("45.50"),
        description="Electricity",
        type="expense",
        transaction_date=date(2026, 6, 3),
        tags=[],
        created_at=datetime(2026, 6, 3, 12, 0, 0),
        updated_at=datetime(2026, 6, 3, 12, 0, 0),
    )
    service.repo.create = AsyncMock(return_value=mock_tx)
    service.audit_service.log_action = AsyncMock()

    data = TransactionCreate(
        amount=Decimal("45.50"),
        description="Electricity",
        transaction_date="2026-06-03",
        category_id=1,
        type="expense",
    )
    res = await service.create(data, user_id=1)

    assert res.amount == Decimal("45.50")
    service.category_repo.get_by_id.assert_called_once_with(1)
    service.repo.create.assert_called_once()
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_create_transaction_category_not_found() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.category_repo = MagicMock()

    service.category_repo.get_by_id = AsyncMock(return_value=None)

    data = TransactionCreate(
        amount=Decimal("45.50"),
        description="Electricity",
        transaction_date="2026-06-03",
        category_id=1,
        type="expense",
    )
    with pytest.raises(CategoryNotFoundError):
        await service.create(data, user_id=1)


@pytest.mark.asyncio
async def test_create_transaction_category_access_denied() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.category_repo = MagicMock()

    service.category_repo.get_by_id = AsyncMock(
        return_value=Category(id=1, user_id=2, is_system=False)
    )

    data = TransactionCreate(
        amount=Decimal("45.50"),
        description="Electricity",
        transaction_date="2026-06-03",
        category_id=1,
        type="expense",
    )
    with pytest.raises(AccessDeniedError):
        await service.create(data, user_id=1)


@pytest.mark.asyncio
async def test_get_filtered_returns_tuple() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()

    service.repo.get_filtered = AsyncMock(return_value=([], 0))

    filters = TransactionFilters()
    items, total = await service.get_filtered(
        user_id=1, filters=filters, offset=0, limit=20
    )

    assert items == []
    assert total == 0


@pytest.mark.asyncio
async def test_get_by_id_with_category_success() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()

    mock_tx = Transaction(
        id=1,
        user_id=1,
        category_id=1,
        amount=Decimal("100"),
        description="test",
        type="expense",
        transaction_date=date(2026, 6, 3),
        tags=[],
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    service.repo.get_with_category = AsyncMock(return_value=mock_tx)

    res = await service.get_by_id_with_category(1, 1)
    assert res.id == 1
    service.repo.get_with_category.assert_called_once_with(1, 1)


@pytest.mark.asyncio
async def test_get_by_id_with_category_not_found() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()

    service.repo.get_with_category = AsyncMock(return_value=None)
    with pytest.raises(TransactionNotFoundError):
        await service.get_by_id_with_category(99, 1)


@pytest.mark.asyncio
async def test_update_transaction_success() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()
    service.category_repo = MagicMock()
    service.audit_service = MagicMock()

    mock_tx = Transaction(
        id=1,
        user_id=1,
        category_id=1,
        amount=Decimal("10.00"),
        description="old",
        type="expense",
        transaction_date=date(2026, 6, 3),
        created_at=datetime(2026, 6, 3, 12, 0, 0),
        updated_at=datetime(2026, 6, 3, 12, 0, 0),
    )
    updated_tx = Transaction(
        id=1,
        user_id=1,
        category_id=2,
        amount=Decimal("10.00"),
        description="new",
        type="expense",
        transaction_date=date(2026, 6, 3),
        tags=[],
        created_at=datetime(2026, 6, 3, 12, 0, 0),
        updated_at=datetime(2026, 6, 3, 12, 0, 0),
    )
    service.repo.get_by_id = AsyncMock(return_value=mock_tx)
    service.category_repo.get_by_id = AsyncMock(return_value=Category(id=2, user_id=1))
    service.repo.update = AsyncMock(return_value=updated_tx)
    service.audit_service.log_action = AsyncMock()

    update_data = TransactionUpdate(category_id=2, description="new")
    await service.update(1, update_data, 1)

    service.repo.update.assert_called_once()
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_update_transaction_not_found() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(TransactionNotFoundError):
        await service.update(99, TransactionUpdate(amount=Decimal("1")), 1)


@pytest.mark.asyncio
async def test_update_transaction_access_denied() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()

    mock_tx = Transaction(id=1, user_id=2)
    service.repo.get_by_id = AsyncMock(return_value=mock_tx)
    with pytest.raises(AccessDeniedError):
        await service.update(1, TransactionUpdate(amount=Decimal("1")), 1)


@pytest.mark.asyncio
async def test_update_transaction_category_not_found() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()
    service.category_repo = MagicMock()

    mock_tx = Transaction(id=1, user_id=1)
    service.repo.get_by_id = AsyncMock(return_value=mock_tx)
    service.category_repo.get_by_id = AsyncMock(return_value=None)

    with pytest.raises(CategoryNotFoundError):
        await service.update(1, TransactionUpdate(category_id=9), 1)


@pytest.mark.asyncio
async def test_update_transaction_category_access_denied() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()
    service.category_repo = MagicMock()

    mock_tx = Transaction(id=1, user_id=1)
    service.repo.get_by_id = AsyncMock(return_value=mock_tx)
    service.category_repo.get_by_id = AsyncMock(
        return_value=Category(id=9, user_id=2, is_system=False)
    )

    with pytest.raises(AccessDeniedError):
        await service.update(1, TransactionUpdate(category_id=9), 1)


@pytest.mark.asyncio
async def test_soft_delete_transaction_success() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()
    service.audit_service = MagicMock()

    mock_tx = Transaction(id=1, user_id=1)
    service.repo.get_by_id = AsyncMock(return_value=mock_tx)
    service.repo.soft_delete = AsyncMock()
    service.audit_service.log_action = AsyncMock()

    await service.soft_delete(1, 1)
    service.repo.soft_delete.assert_called_once_with(1)
    service.audit_service.log_action.assert_called_once()


@pytest.mark.asyncio
async def test_soft_delete_transaction_not_found() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()

    service.repo.get_by_id = AsyncMock(return_value=None)
    with pytest.raises(TransactionNotFoundError):
        await service.soft_delete(99, 1)


@pytest.mark.asyncio
async def test_soft_delete_transaction_access_denied() -> None:
    db = MagicMock(spec=AsyncSession)
    service = TransactionService(db)
    service.repo = MagicMock()

    mock_tx = Transaction(id=1, user_id=2)
    service.repo.get_by_id = AsyncMock(return_value=mock_tx)
    with pytest.raises(AccessDeniedError):
        await service.soft_delete(1, 1)
