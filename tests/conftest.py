import asyncio
import os
from collections.abc import AsyncGenerator, Generator
from contextlib import suppress

import pytest
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Set test environment variables BEFORE importing app parts
os.environ["DATABASE_URL"] = (
    "postgresql://spendwise:spendwise_dev_password@localhost:5432/spendwise_test"
)
os.environ["REDIS_URL"] = "redis://localhost:6379/1"
os.environ["SECRET_KEY"] = (
    "2e8a551d6dd3ae3e4e2c461948784821ff3e4b8e6384747e680ea2569bd88f52"
)
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/1"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/1"
os.environ["ENVIRONMENT"] = "development"

import app.models
from app.api.deps import get_db
from app.core.config import settings
from app.core.security import create_access_token
from app.db.base import Base
from app.main import app as fastapi_app
from app.worker.celery_app import celery_app
from tests.factories.category import CategoryFactory
from tests.factories.transaction import TransactionFactory
from tests.factories.user import UserFactory

celery_app.conf.task_always_eager = True

# Create test engine and sessionmaker
test_engine: AsyncEngine = create_async_engine(
    settings.ASYNC_DATABASE_URL,
    echo=False,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
def setup_cache() -> Generator[None, None, None]:
    FastAPICache.init(InMemoryBackend())
    yield


@pytest.fixture(scope="session", autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    # Set up tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Clean up tables
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function", autouse=True)
async def clear_redis() -> AsyncGenerator[None, None]:
    from app.core.redis import redis_client

    with suppress(Exception):
        await redis_client.flushdb()

    yield


@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestAsyncSessionLocal() as session:
        await session.begin()

        async def mock_commit() -> None:
            await session.flush()

        session.commit = mock_commit  # type: ignore[method-assign]

        yield session

        await session.rollback()


@pytest.fixture(scope="function", autouse=True)
async def override_get_db(db_session: AsyncSession) -> AsyncGenerator[None, None]:
    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    fastapi_app.dependency_overrides[get_db] = _override_get_db
    yield
    fastapi_app.dependency_overrides.clear()


@pytest.fixture(scope="function")
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app),
        base_url="http://test",
    ) as ac:
        yield ac


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession) -> app.models.User:
    user = UserFactory.build(is_verified=False)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture(scope="function")
async def verified_user(db_session: AsyncSession) -> app.models.User:
    user = UserFactory.build(is_verified=True)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture(scope="function")
async def admin_user(db_session: AsyncSession) -> app.models.User:
    user = UserFactory.build(is_verified=True, is_superuser=True)
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture(scope="function")
def auth_headers() -> Generator[callable, None, None]:
    def _headers(user: app.models.User) -> dict[str, str]:
        token = create_access_token(subject=str(user.id))
        return {"Authorization": f"Bearer {token}"}

    yield _headers


@pytest.fixture(scope="function")
async def test_category(
    db_session: AsyncSession, verified_user: app.models.User
) -> app.models.Category:
    category = CategoryFactory.build(user=verified_user, type="expense")
    db_session.add(category)
    await db_session.flush()
    return category


@pytest.fixture(scope="function")
async def test_transaction(
    db_session: AsyncSession,
    verified_user: app.models.User,
    test_category: app.models.Category,
) -> app.models.Transaction:
    transaction = TransactionFactory.build(
        user=verified_user,
        category=test_category,
        type="expense",
    )
    db_session.add(transaction)
    await db_session.flush()
    return transaction
