from unittest.mock import AsyncMock

import pytest

from scripts import capacity_environment


@pytest.fixture
def capacity_host(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    monkeypatch.setenv("CAPACITY_PROJECT", "spendwise-capacity-isolated")
    monkeypatch.setenv("CAPACITY_POSTGRES_ID", "pg")
    monkeypatch.setenv("CAPACITY_REDIS_ID", "redis")
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:16381/0")
    monkeypatch.setattr(
        capacity_environment,
        "published_port",
        lambda _, service, __: {
            "postgres": 15434,
            "redis": 16381,
        }[service],
    )
    monkeypatch.setattr(capacity_environment, "docker_output", lambda *_: "100")
    connection = AsyncMock()
    connection.fetchval.return_value = "100"
    monkeypatch.setattr(
        capacity_environment.asyncpg, "connect", AsyncMock(return_value=connection)
    )
    return connection


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://spendwise@127.0.0.1:15432/spendwise",
        "postgresql://spendwise_capacity@example.com:15434/spendwise_capacity",
        "postgresql://spendwise_capacity@127.0.0.1:15434/spendwise_capacity?host=example.com",
    ],
)
@pytest.mark.usefixtures("capacity_host")
async def test_refuses_non_capacity_urls(monkeypatch, database_url):
    monkeypatch.setenv("DATABASE_URL", database_url)
    with pytest.raises(RuntimeError, match="Refusing capacity operation"):
        await capacity_environment.verify_capacity_environment()
    capacity_environment.asyncpg.connect.assert_not_awaited()


@pytest.mark.parametrize("identity", ["100", "200"])
async def test_checks_actual_postgres_identity(monkeypatch, capacity_host, identity):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://spendwise_capacity@127.0.0.1:15434/spendwise_capacity",
    )
    capacity_host.fetchval.return_value = identity
    if identity == "100":
        await capacity_environment.verify_capacity_environment()
    else:
        with pytest.raises(RuntimeError, match="Refusing capacity operation"):
            await capacity_environment.verify_capacity_environment()
    capacity_host.close.assert_awaited_once()
