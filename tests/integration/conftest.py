import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy.ext.asyncio import AsyncSession

from alembic import command
from app.api.deps import get_db
from app.core.rate_limit import limiter
from app.db.session import run_after_commit
from app.main import app
from tests.conftest import TestAsyncSessionLocal, test_engine


@pytest.fixture(scope="session", autouse=True)
async def migrate_test_db() -> AsyncGenerator[None, None]:
    await asyncio.to_thread(command.upgrade, Config("alembic.ini"), "head")
    yield
    await test_engine.dispose()


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_engine.connect() as connection:
        transaction = await connection.begin()
        async with TestAsyncSessionLocal(
            bind=connection, join_transaction_mode="create_savepoint"
        ) as session:
            yield session
        await transaction.rollback()


@pytest.fixture(autouse=True)
async def isolate_api(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncGenerator[None, None]:
    monkeypatch.setattr(limiter, "_key_prefix", f"test-{uuid4().hex}")
    for task in ("send_verification_email", "send_password_reset_email"):
        monkeypatch.setattr(f"app.worker.tasks.{task}.apply_async", MagicMock())

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        try:
            yield db_session
            await db_session.commit()
            await run_after_commit(db_session)
        except Exception:
            db_session.info.pop("spendwise_after_commit", None)
            await db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
