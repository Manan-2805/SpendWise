from datetime import date
from decimal import Decimal

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from tests.factories.category import CategoryFactory
from tests.factories.transaction import TransactionFactory
from tests.factories.user import UserFactory


async def test_list_transactions_filters(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)

    # Create category
    category = CategoryFactory.build(user=verified_user, name="Dining")
    db_session.add(category)
    await db_session.flush()

    # Create multiple transactions
    tx1 = TransactionFactory.build(
        user=verified_user,
        category=category,
        amount=Decimal("50.00"),
        type="expense",
        transaction_date=date(2026, 6, 1),
        description="Lunch",
    )
    tx2 = TransactionFactory.build(
        user=verified_user,
        category=category,
        amount=Decimal("150.00"),
        type="expense",
        transaction_date=date(2026, 6, 2),
        description="Dinner party",
    )
    db_session.add_all([tx1, tx2])
    await db_session.flush()

    # Test filtering by min_amount
    response = await client.get(
        "/api/v1/transactions/?min_amount=100.00", headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["description"] == "Dinner party"

    # Test filtering by date range
    response = await client.get(
        "/api/v1/transactions/?date_from=2026-06-01&date_to=2026-06-01", headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["description"] == "Lunch"


async def test_create_transaction_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    category = CategoryFactory.build(user=verified_user, name="Groceries")
    db_session.add(category)
    await db_session.flush()

    payload = {
        "amount": "25.50",
        "description": "Weekly grocery list",
        "transaction_date": "2026-06-03",
        "type": "expense",
        "category_id": category.id,
        "notes": "Purchased organic milk and apples.",
        "tags": ["organic", "groceries"],
    }
    response = await client.post("/api/v1/transactions/", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["description"] == "Weekly grocery list"
    assert data["amount"] == "25.50"

    # Verify DB
    result = await db_session.execute(
        select(Transaction).where(Transaction.id == data["id"])
    )
    tx = result.scalar_one_or_none()
    assert tx is not None
    assert tx.amount == Decimal("25.50")


@pytest.mark.usefixtures("db_session")
async def test_create_transaction_invalid_category(
    client: AsyncClient, verified_user: User, auth_headers: callable
) -> None:
    headers = auth_headers(verified_user)
    payload = {
        "amount": "100.00",
        "description": "Ghost Category Tx",
        "transaction_date": "2026-06-03",
        "type": "expense",
        "category_id": 99999,  # Non-existent category
    }
    response = await client.post("/api/v1/transactions/", json=payload, headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "CATEGORY_NOT_FOUND"


@pytest.mark.usefixtures("db_session")
async def test_create_transaction_rejects_mismatched_category_type(
    client: AsyncClient,
    verified_user: User,
    auth_headers: callable,
    test_category: Category,
) -> None:
    response = await client.post(
        "/api/v1/transactions/",
        headers=auth_headers(verified_user),
        json={
            "category_id": test_category.id,
            "amount": "25.50",
            "description": "Income under an expense category",
            "transaction_date": "2026-06-03",
            "type": "income",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


@pytest.mark.parametrize("change", ["type", "category"])
async def test_update_transaction_rejects_mismatched_category_type(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
    test_transaction: Transaction,
    change: str,
) -> None:
    income_category = CategoryFactory.build(user=verified_user, type="income")
    db_session.add(income_category)
    await db_session.flush()

    payload = (
        {"type": "income"} if change == "type" else {"category_id": income_category.id}
    )
    response = await client.patch(
        f"/api/v1/transactions/{test_transaction.id}",
        headers=auth_headers(verified_user),
        json=payload,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


@pytest.mark.usefixtures("db_session")
async def test_get_transaction_success(
    client: AsyncClient,
    verified_user: User,
    auth_headers: callable,
    test_transaction: Transaction,
) -> None:
    headers = auth_headers(verified_user)
    response = await client.get(
        f"/api/v1/transactions/{test_transaction.id}", headers=headers
    )
    assert response.status_code == 200

    data = response.json()
    assert data["id"] == test_transaction.id
    assert "category" in data
    assert data["category"]["name"] == test_transaction.category.name


async def test_get_transaction_unauthorized_404(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)

    # Create transaction for another user
    other_user = UserFactory.build(is_verified=True)
    other_cat = CategoryFactory.build(user=other_user, name="Other Cat")
    other_tx = TransactionFactory.build(
        user=other_user, category=other_cat, description="Secret Tx"
    )
    db_session.add_all([other_user, other_cat, other_tx])
    await db_session.flush()

    # User A tries to view User B's transaction -> returns 404
    response = await client.get(f"/api/v1/transactions/{other_tx.id}", headers=headers)
    assert response.status_code == 404
    assert response.json()["code"] == "TRANSACTION_NOT_FOUND"


async def test_update_transaction_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
    test_transaction: Transaction,
) -> None:
    headers = auth_headers(verified_user)
    payload = {"amount": "99.99", "description": "Updated Description"}

    response = await client.patch(
        f"/api/v1/transactions/{test_transaction.id}", json=payload, headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["amount"] == "99.99"
    assert data["description"] == "Updated Description"

    await db_session.refresh(test_transaction)
    assert test_transaction.amount == Decimal("99.99")
    assert test_transaction.description == "Updated Description"


async def test_delete_transaction_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
    test_transaction: Transaction,
) -> None:
    headers = auth_headers(verified_user)
    response = await client.delete(
        f"/api/v1/transactions/{test_transaction.id}", headers=headers
    )
    assert response.status_code == 204

    # Verify soft delete
    await db_session.refresh(test_transaction)
    assert test_transaction.deleted_at is not None
