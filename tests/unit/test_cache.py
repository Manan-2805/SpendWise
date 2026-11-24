import json
from unittest.mock import AsyncMock, patch

from redis.exceptions import RedisError

from app.core.cache import RELEASE_LOCK, get_or_set_cache


async def test_cache_skips_factory_on_hit() -> None:
    factory = AsyncMock()
    with patch(
        "app.core.redis.redis_client.get", AsyncMock(return_value=json.dumps("hit"))
    ):
        assert await get_or_set_cache("some-key", factory) == "hit"
    factory.assert_not_awaited()


async def test_cache_returns_factory_value_during_redis_outage() -> None:
    factory = AsyncMock(return_value="fresh")
    with patch("app.core.redis.redis_client.get", AsyncMock(side_effect=RedisError)):
        assert await get_or_set_cache("some-key", factory) == "fresh"
    factory.assert_awaited_once()


async def test_cache_rechecks_after_acquiring_lock_and_releases_only_its_owner() -> (
    None
):
    factory = AsyncMock()
    get = AsyncMock(side_effect=[None, json.dumps("late")])
    set_value = AsyncMock(return_value=True)
    release = AsyncMock()
    with (
        patch("app.core.redis.redis_client.get", get),
        patch("app.core.redis.redis_client.set", set_value),
        patch("app.core.redis.redis_client.eval", release),
    ):
        assert await get_or_set_cache("some-key", factory) == "late"
    factory.assert_not_awaited()
    lock, owner = set_value.await_args.args
    release.assert_awaited_once_with(RELEASE_LOCK, 1, lock, owner)


async def test_cache_replaces_invalid_json() -> None:
    factory = AsyncMock(return_value="fresh")
    set_value = AsyncMock(return_value=True)
    with (
        patch(
            "app.core.redis.redis_client.get", AsyncMock(return_value="invalid-json")
        ),
        patch("app.core.redis.redis_client.set", set_value),
        patch("app.core.redis.redis_client.eval", AsyncMock()),
    ):
        assert await get_or_set_cache("some-key", factory) == "fresh"
    factory.assert_awaited_once()
    assert set_value.await_args.args == ("some-key", json.dumps("fresh"))


async def test_cache_lock_timeout_falls_back_to_factory() -> None:
    factory = AsyncMock(return_value="fresh")
    with (
        patch("app.core.redis.redis_client.get", AsyncMock(return_value=None)),
        patch("app.core.redis.redis_client.set", AsyncMock(return_value=False)),
    ):
        assert await get_or_set_cache("some-key", factory) == "fresh"
    factory.assert_awaited_once()
