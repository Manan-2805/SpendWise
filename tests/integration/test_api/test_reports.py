from datetime import date
from decimal import Decimal

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache_keys import REPORT_MONTHLY
from app.core.redis import redis_client
from app.models.user import User
from tests.factories.category import CategoryFactory
from tests.factories.transaction import TransactionFactory


async def test_monthly_summary_real_db(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)

    # Create system categories or user categories
    cat_inc = CategoryFactory.build(user=verified_user, name="Salary", type="income")
    cat_exp = CategoryFactory.build(user=verified_user, name="Rent", type="expense")
    db_session.add_all([cat_inc, cat_exp])
    await db_session.flush()

    # Create transactions
    tx_inc = TransactionFactory.build(
        user=verified_user,
        category=cat_inc,
        amount=Decimal("3000.00"),
        type="income",
        transaction_date=date(2026, 6, 1),
    )
    tx_exp = TransactionFactory.build(
        user=verified_user,
        category=cat_exp,
        amount=Decimal("1200.00"),
        type="expense",
        transaction_date=date(2026, 6, 15),
    )
    db_session.add_all([tx_inc, tx_exp])
    await db_session.flush()

    response = await client.get(
        "/api/v1/reports/monthly-summary?year=2026&month=6", headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["income"] == "3000.00"
    assert data["expense"] == "1200.00"
    assert data["balance"] == "1800.00"


async def test_category_rename_and_reassignment_refresh_cached_reports(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    source = CategoryFactory.build(user=verified_user, name="Food", type="expense")
    target = CategoryFactory.build(user=verified_user, name="Household", type="expense")
    transaction = TransactionFactory.build(
        user=verified_user,
        category=source,
        amount=Decimal("24.50"),
        type="expense",
        transaction_date=date(2026, 6, 5),
    )
    db_session.add_all([source, target, transaction])
    await db_session.flush()

    headers = auth_headers(verified_user)
    monthly = "/api/v1/reports/monthly-summary?year=2026&month=6"
    breakdown = (
        "/api/v1/reports/category-breakdown?date_from=2026-06-01&date_to=2026-06-30"
    )
    key = REPORT_MONTHLY.format(user_id=verified_user.id, year=2026, month=6)
    version = verified_user.cache_version

    initial = await client.get(monthly, headers=headers)
    assert initial.status_code == 200
    assert initial.json()["expense"] == "24.50"
    assert await redis_client.exists(f"{key}:v{version}")
    initial_breakdown = await client.get(breakdown, headers=headers)
    assert initial_breakdown.status_code == 200
    assert [item["category_name"] for item in initial_breakdown.json()] == ["Food"]

    renamed = await client.patch(
        f"/api/v1/categories/{source.id}", headers=headers, json={"name": "Groceries"}
    )
    assert renamed.status_code == 200

    # Category edits preserve monthly totals, but the summary must use a fresh key.
    after_rename = await client.get(monthly, headers=headers)
    assert after_rename.status_code == 200
    assert after_rename.json() == initial.json()
    assert await redis_client.exists(f"{key}:v{version + 1}")
    renamed_breakdown = await client.get(breakdown, headers=headers)
    assert renamed_breakdown.status_code == 200
    assert [item["category_name"] for item in renamed_breakdown.json()] == ["Groceries"]

    reassigned = await client.delete(
        f"/api/v1/categories/{source.id}",
        headers=headers,
        params={"reassign_to_id": target.id},
    )
    assert reassigned.status_code == 204

    after_reassignment = await client.get(monthly, headers=headers)
    assert after_reassignment.status_code == 200
    assert after_reassignment.json() == initial.json()
    assert await redis_client.exists(f"{key}:v{version + 2}")
    reassigned_breakdown = await client.get(breakdown, headers=headers)
    assert reassigned_breakdown.status_code == 200
    assert [
        (item["category_name"], item["total"]) for item in reassigned_breakdown.json()
    ] == [("Household", "24.50")]


async def test_category_breakdown_real_db(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)

    cat1 = CategoryFactory.build(user=verified_user, name="Food", type="expense")
    cat2 = CategoryFactory.build(user=verified_user, name="Utilities", type="expense")
    db_session.add_all([cat1, cat2])
    await db_session.flush()

    tx1 = TransactionFactory.build(
        user=verified_user,
        category=cat1,
        amount=Decimal("100.00"),
        type="expense",
        transaction_date=date(2026, 6, 5),
    )
    tx2 = TransactionFactory.build(
        user=verified_user,
        category=cat2,
        amount=Decimal("300.00"),
        type="expense",
        transaction_date=date(2026, 6, 6),
    )
    db_session.add_all([tx1, tx2])
    await db_session.flush()

    response = await client.get(
        "/api/v1/reports/category-breakdown?date_from=2026-06-01&date_to=2026-06-30&type=expense",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2

    # Verify percentages: 100/400 = 25%, 300/400 = 75%
    breakdown = {item["category_name"]: item for item in data}
    assert float(breakdown["Food"]["total"]) == 100.0
    assert float(breakdown["Food"]["percentage"]) == 25.0
    assert float(breakdown["Utilities"]["total"]) == 300.0
    assert float(breakdown["Utilities"]["percentage"]) == 75.0


async def test_balance_trend_real_db(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)

    cat = CategoryFactory.build(user=verified_user, name="Misc", type="expense")
    db_session.add(cat)
    await db_session.flush()

    tx = TransactionFactory.build(
        user=verified_user,
        category=cat,
        amount=Decimal("50.00"),
        type="expense",
        transaction_date=date(2026, 6, 10),
    )
    db_session.add(tx)
    await db_session.flush()

    response = await client.get(
        "/api/v1/reports/balance-trend?date_from=2026-06-01&date_to=2026-06-30",
        headers=headers,
    )
    assert response.status_code == 200
    data = response.json()
    # Let's verify trend is returned
    assert len(data) > 0
    assert data[0]["expense"] == "50.00"
