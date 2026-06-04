from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.user import User
from tests.factories.category import CategoryFactory
from tests.factories.user import UserFactory


async def test_list_categories_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    # Create two categories for verified_user
    cat1 = CategoryFactory.build(user=verified_user, name="Category 1")
    cat2 = CategoryFactory.build(user=verified_user, name="Category 2")
    db_session.add_all([cat1, cat2])
    await db_session.flush()

    response = await client.get("/api/v1/categories/", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Should contain the two categories
    names = [cat["name"] for cat in data]
    assert "Category 1" in names
    assert "Category 2" in names


async def test_create_category_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    payload = {
        "name": "Entertainment",
        "description": "Movies & Games",
        "color": "#FF0055",
        "icon": "film",
        "type": "expense",
    }
    response = await client.post("/api/v1/categories/", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Entertainment"
    assert data["user_id"] == verified_user.id

    # Verify in DB
    result = await db_session.execute(select(Category).where(Category.id == data["id"]))
    cat = result.scalar_one_or_none()
    assert cat is not None
    assert cat.name == "Entertainment"


async def test_create_duplicate_category(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    cat1 = CategoryFactory.build(user=verified_user, name="Duplicated")
    db_session.add(cat1)
    await db_session.flush()

    payload = {
        "name": "Duplicated",
        "description": "Diff desc",
        "color": "#000000",
        "icon": "icon",
        "type": "expense",
    }
    response = await client.post("/api/v1/categories/", json=payload, headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"


async def test_get_category_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    cat = CategoryFactory.build(user=verified_user, name="Specific Cat")
    db_session.add(cat)
    await db_session.flush()

    response = await client.get(f"/api/v1/categories/{cat.id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["name"] == "Specific Cat"


async def test_get_category_access_denied(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)

    # Create another user and their category
    other_user = UserFactory.build(is_verified=True)
    other_cat = CategoryFactory.build(user=other_user, name="Other User Cat")
    db_session.add_all([other_user, other_cat])
    await db_session.flush()

    # Try to access other user's category
    response = await client.get(f"/api/v1/categories/{other_cat.id}", headers=headers)
    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_DENIED"


async def test_update_category_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    cat = CategoryFactory.build(user=verified_user, name="Old Name", color="#111111")
    db_session.add(cat)
    await db_session.flush()

    payload = {"name": "New Name", "color": "#222222"}
    response = await client.patch(
        f"/api/v1/categories/{cat.id}", json=payload, headers=headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "New Name"
    assert data["color"] == "#222222"

    await db_session.refresh(cat)
    assert cat.name == "New Name"


async def test_delete_category_with_reassign_success(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)

    # Create Category A and Category B
    cat_a = CategoryFactory.build(user=verified_user, name="Cat A")
    cat_b = CategoryFactory.build(user=verified_user, name="Cat B")
    db_session.add_all([cat_a, cat_b])
    await db_session.flush()

    # Delete Cat A and reassign to Cat B
    response = await client.delete(
        f"/api/v1/categories/{cat_a.id}?reassign_to_id={cat_b.id}", headers=headers
    )
    assert response.status_code == 204

    # Verify Cat A is soft-deleted
    await db_session.refresh(cat_a)
    assert cat_a.deleted_at is not None


async def test_get_category_not_found(
    client: AsyncClient, verified_user: User, auth_headers: callable
) -> None:
    headers = auth_headers(verified_user)
    response = await client.get("/api/v1/categories/9999", headers=headers)
    assert response.status_code == 404


async def test_update_category_not_found(
    client: AsyncClient, verified_user: User, auth_headers: callable
) -> None:
    headers = auth_headers(verified_user)
    response = await client.patch(
        "/api/v1/categories/9999", json={"name": "New"}, headers=headers
    )
    assert response.status_code == 404


async def test_update_category_access_denied(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    other_user = UserFactory.build(is_verified=True)
    other_cat = CategoryFactory.build(user=other_user, name="Other User Cat")
    db_session.add_all([other_user, other_cat])
    await db_session.flush()

    response = await client.patch(
        f"/api/v1/categories/{other_cat.id}", json={"name": "New"}, headers=headers
    )
    assert response.status_code == 403


async def test_delete_category_not_found(
    client: AsyncClient, verified_user: User, auth_headers: callable
) -> None:
    headers = auth_headers(verified_user)
    response = await client.delete("/api/v1/categories/9999", headers=headers)
    assert response.status_code == 404


async def test_delete_category_access_denied(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    other_user = UserFactory.build(is_verified=True)
    other_cat = CategoryFactory.build(user=other_user, name="Other User Cat")
    db_session.add_all([other_user, other_cat])
    await db_session.flush()

    response = await client.delete(
        f"/api/v1/categories/{other_cat.id}", headers=headers
    )
    assert response.status_code == 403


async def test_delete_category_active_transactions_no_reassign(
    client: AsyncClient,
    db_session: AsyncSession,
    verified_user: User,
    auth_headers: callable,
) -> None:
    headers = auth_headers(verified_user)
    cat = CategoryFactory.build(user=verified_user, name="To Delete")
    db_session.add(cat)
    await db_session.flush()

    from tests.factories.transaction import TransactionFactory

    # Create an active transaction under this category
    tx = TransactionFactory.build(user=verified_user, category=cat, amount=100.0)
    db_session.add(tx)
    await db_session.flush()

    response = await client.delete(f"/api/v1/categories/{cat.id}", headers=headers)
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT"
