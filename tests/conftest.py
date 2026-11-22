import asyncio
import os
import secrets
from collections.abc import AsyncGenerator, Generator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# Set test environment variables BEFORE importing app parts
os.environ["DATABASE_URL"] = (
    "postgresql://spendwise_test:spendwise_test_local@127.0.0.1:"
    f"{os.getenv('TEST_POSTGRES_PORT', '55432')}/spendwise_test"
)
os.environ["REDIS_URL"] = f"redis://127.0.0.1:{os.getenv('TEST_REDIS_PORT', '56379')}/0"
os.environ["CELERY_BROKER_URL"] = (
    f"redis://127.0.0.1:{os.getenv('TEST_REDIS_PORT', '56379')}/1"
)
os.environ["CELERY_RESULT_BACKEND"] = (
    f"redis://127.0.0.1:{os.getenv('TEST_REDIS_PORT', '56379')}/2"
)
os.environ["SECRET_KEY"] = secrets.token_hex(32)
os.environ["ENVIRONMENT"] = "development"
os.environ["DEBUG"] = "false"
os.environ["SMTP_HOST"] = ""

import app.models
from app.core.config import settings
from app.core.security import create_access_token
from app.main import app as fastapi_app
from app.worker.celery_app import celery_app
from tests.factories.category import CategoryFactory
from tests.factories.transaction import TransactionFactory
from tests.factories.user import UserFactory

celery_app.conf.task_always_eager = True

# Create test engine and sessionmaker
test_engine = create_async_engine(
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
