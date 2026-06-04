import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import AsyncClient

from app.api.v1.endpoints.health import check_celery_sync, check_db, check_redis


async def test_health_check_endpoints(client: AsyncClient) -> None:
    # Shallow liveness probe
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

    # Alive liveness probe
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}

    # Readiness probe - success case
    with (
        patch("app.api.v1.endpoints.health.check_db", return_value=True),
        patch("app.api.v1.endpoints.health.check_redis", return_value=True),
        patch("app.api.v1.endpoints.health.check_celery", return_value=True),
    ):
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 200
        assert response.json() == {
            "status": "ready",
            "db": "up",
            "redis": "up",
            "celery": "up",
        }

    # Readiness probe - failure case
    with (
        patch("app.api.v1.endpoints.health.check_db", return_value=False),
        patch("app.api.v1.endpoints.health.check_redis", return_value=False),
        patch("app.api.v1.endpoints.health.check_celery", return_value=False),
    ):
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "db": "down",
            "redis": "down",
            "celery": "down",
        }

    # Readiness probe - timeout case
    async def mock_timeout():
        await asyncio.sleep(1)
        return True

    with (
        patch("app.api.v1.endpoints.health.check_db", side_effect=mock_timeout),
        patch("app.api.v1.endpoints.health.check_redis", side_effect=mock_timeout),
        patch("app.api.v1.endpoints.health.check_celery", side_effect=mock_timeout),
    ):
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 503
        assert response.json() == {
            "status": "not_ready",
            "db": "down",
            "redis": "down",
            "celery": "down",
        }


async def test_health_check_helpers() -> None:
    from tests.conftest import TestAsyncSessionLocal

    # Test helper functions directly
    with patch("app.api.v1.endpoints.health.AsyncSessionLocal", TestAsyncSessionLocal):
        assert await check_db() is True
    assert await check_redis() is True

    # Test failure path of helper functions
    with patch("app.api.v1.endpoints.health.AsyncSessionLocal", side_effect=Exception):
        assert await check_db() is False

    # Mock ping_redis return value as an AsyncMock to avoid TypeError / closed loop issues
    with patch("app.api.v1.endpoints.health.ping_redis", AsyncMock(return_value=False)):
        assert await check_redis() is False

    # Test celery check sync
    mock_conn = MagicMock()
    with patch(
        "app.worker.celery_app.celery_app.connection_for_write", return_value=mock_conn
    ):
        assert check_celery_sync() is True

    with patch(
        "app.worker.celery_app.celery_app.connection_for_write", side_effect=Exception
    ):
        assert check_celery_sync() is False
