from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


async def test_base_repository_extended_crud(db_session: AsyncSession) -> None:
    # Set up repo
    repo = BaseRepository(User, db_session)

    # Test count initially
    c_init = await repo.count()
    assert c_init == 0

    # Test create
    user = await repo.create(
        email="base_repo@example.com",
        username="base_repo",
        hashed_password="hashed_password",
        is_active=True,
    )
    assert user.id is not None

    # Test count with filter
    assert await repo.count(email="base_repo@example.com") == 1
    assert await repo.count(email="nonexistent@example.com") == 0

    # Test get_all with order_by asc
    users = await repo.get_all(order_by="username", descending=False)
    assert len(users) == 1
    assert users[0].username == "base_repo"

    # Test get_all with order_by desc
    users_desc = await repo.get_all(order_by="username", descending=True)
    assert len(users_desc) == 1

    # Test update nonexistent
    assert await repo.update(9999, username="foo") is None

    # Test soft delete nonexistent
    assert await repo.soft_delete(9999) is False

    # Test hard_delete nonexistent
    assert await repo.hard_delete(9999) is False

    # Test hard delete existent
    assert await repo.hard_delete(user.id) is True
