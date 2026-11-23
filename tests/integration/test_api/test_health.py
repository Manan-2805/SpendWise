import asyncio
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.rate_limit import limiter
from app.main import app


async def test_liveness_skips_database_and_redis(client: AsyncClient) -> None:
    with (
        patch.object(
            limiter, "_check_request_limit", side_effect=AssertionError
        ) as rate_limit,
        patch(
            "app.db.session.AsyncSessionLocal", side_effect=AssertionError
        ) as session,
        patch("app.core.redis.redis_client.ping", side_effect=AssertionError) as ping,
    ):
        for suffix, status in (("", "ok"), ("/live", "alive")):
            response = await client.get(f"/api/v1/health{suffix}")
            assert response.status_code == 200
            assert response.json() == {"status": status}
    rate_limit.assert_not_called()
    session.assert_not_called()
    ping.assert_not_called()


async def test_readiness_uses_snapshot_across_requests(
    client: AsyncClient, monkeypatch
) -> None:
    from app.core.health import Readiness

    db, redis, broker = (AsyncMock(return_value=True) for _ in range(3))
    monitor = Readiness(db, redis, broker, interval=2, timeout=0.01, max_age=6)
    monkeypatch.setattr(app.state, "readiness", monitor, raising=False)
    path = "/api/v1/health/ready"
    assert (await client.get(path)).status_code == 503
    await monitor.refresh()
    with patch.object(
        limiter, "_check_request_limit", side_effect=AssertionError
    ) as rate_limit:
        for _ in range(2):
            response = await client.get(path)
            assert response.status_code == 200
            assert response.json() == {
                "status": "ready",
                "db": "up",
                "redis": "up",
                "celery": "up",
            }
    rate_limit.assert_not_called()
    for probe in (db, redis, broker):
        probe.assert_awaited_once()

    db.side_effect = OSError()
    redis.return_value = False

    async def stall() -> bool:
        await asyncio.sleep(1)
        return True

    broker.side_effect = stall
    await monitor.refresh()
    response = await client.get(path)
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "db": "down",
        "redis": "down",
        "celery": "down",
    }
    db.side_effect = broker.side_effect = None
    redis.return_value = True
    await monitor.refresh()
    assert (await client.get(path)).status_code == 200
    with patch("app.core.health.monotonic", return_value=monitor.updated_at + 7):
        assert (await client.get(path)).status_code == 503


async def test_readiness_refreshes_in_background_and_cancels() -> None:
    from app.core.health import Readiness

    sampled = asyncio.Event()
    probe = AsyncMock(return_value=True)

    async def sampled_db() -> bool:
        sampled.set()
        return True

    monitor = Readiness(
        sampled_db, probe, probe, interval=0.001, timeout=0.05, max_age=1
    )
    task = asyncio.create_task(monitor.run())
    try:
        await asyncio.wait_for(sampled.wait(), timeout=1)
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
    assert task.cancelled()


async def test_readiness_has_a_separate_database_pool() -> None:
    from app.core.health import monitor_readiness

    request_engine = create_async_engine(
        settings.ASYNC_DATABASE_URL, pool_size=1, max_overflow=0, pool_timeout=0.01
    )
    try:
        with patch(
            "app.db.session.AsyncSessionLocal", async_sessionmaker(request_engine)
        ):
            async with request_engine.connect(), monitor_readiness() as monitor:
                assert monitor.current() == (True, True, True)
    finally:
        await request_engine.dispose()
