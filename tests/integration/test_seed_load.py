from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from scripts import seed_load_test_db


async def test_capacity_seed_counts_and_can_be_rerun(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    @asynccontextmanager
    async def seed_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    monkeypatch.setattr(seed_load_test_db, "AsyncSessionLocal", seed_session)
    await seed_load_test_db.seed_volume(capacity=True, user_count=2)
    await seed_load_test_db.seed_volume(capacity=True, user_count=2)

    users = select(User.id).where(User.username.startswith("capacity_user_"))
    assert len((await db_session.scalars(users)).all()) == 2
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Category)
            .where(Category.user_id.in_(users))
        )
        == 8
    )
    assert (
        await db_session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(Transaction.user_id.in_(users))
        )
        == 128
    )


async def test_capacity_seed_detects_an_incomplete_dataset(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    @asynccontextmanager
    async def seed_session() -> AsyncIterator[AsyncSession]:
        yield db_session

    db_session.add(
        User(username="capacity_user_1", email="capacity_user_1@example.com")
    )
    await db_session.flush()
    monkeypatch.setattr(seed_load_test_db, "AsyncSessionLocal", seed_session)

    with pytest.raises(RuntimeError, match="Incomplete capacity dataset"):
        await seed_load_test_db.seed_volume(capacity=True, user_count=1)
