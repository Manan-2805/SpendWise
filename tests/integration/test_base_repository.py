from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


async def test_base_repository_extended_crud(db_session: AsyncSession) -> None:
    # Set up repo
    repo = BaseRepository(User, db_session)

    # Test count initially
    c_init = await repo.count()

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
    assert len(users) == c_init + 1
    assert any(item.username == "base_repo" for item in users)
    assert [item.username for item in users] == sorted(item.username for item in users)

    # Test get_all with order_by desc
    users_desc = await repo.get_all(order_by="username", descending=True)
    assert [item.id for item in users_desc] == [item.id for item in reversed(users)]

    # Test update nonexistent
    assert await repo.update(9999, username="foo") is None

    # Test soft delete nonexistent
    assert await repo.soft_delete(9999) is False

    # Test hard_delete nonexistent
    assert await repo.hard_delete(9999) is False

    # Test hard delete existent
    assert await repo.hard_delete(user.id) is True
