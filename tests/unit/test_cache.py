import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.cache import get_or_set_cache, versioned_key_builder


async def test_get_or_set_cache_branches() -> None:
    # Test json load failure fallback
    mock_get = AsyncMock(return_value="invalid-json")
    with patch("app.core.redis.redis_client.get", mock_get):
        val = await get_or_set_cache("some-key", AsyncMock(return_value="factory-val"))
        assert val == "invalid-json"

    # Test lock acquisition failure fallback
    mock_get_none = AsyncMock(return_value=None)
    mock_set_false = AsyncMock(return_value=False)
    with (
        patch("app.core.redis.redis_client.get", mock_get_none),
        patch("app.core.redis.redis_client.set", mock_set_false),
    ):
        mock_factory = AsyncMock(return_value="factory-val")
        val = await get_or_set_cache("some-key", mock_factory)
        assert val == "factory-val"
        mock_factory.assert_called_once()

    # Test lock acquired, but cache populated in between
    # First get returns None, set(lock) returns True, second get returns cached val
    get_mock = AsyncMock(side_effect=[None, json.dumps("late-cached-val")])
    mock_set_true = AsyncMock(return_value=True)
    mock_delete_true = AsyncMock(return_value=True)
    with (
        patch("app.core.redis.redis_client.get", get_mock),
        patch("app.core.redis.redis_client.set", mock_set_true),
        patch("app.core.redis.redis_client.delete", mock_delete_true),
    ):
        mock_factory = AsyncMock()
        val = await get_or_set_cache("some-key", mock_factory)
        assert val == "late-cached-val"
        mock_factory.assert_not_called()

    # Test json loads exception on second get
    get_mock_exc = AsyncMock(side_effect=[None, "late-invalid-json"])
    with (
        patch("app.core.redis.redis_client.get", get_mock_exc),
        patch("app.core.redis.redis_client.set", mock_set_true),
        patch("app.core.redis.redis_client.delete", mock_delete_true),
    ):
        mock_factory = AsyncMock()
        val = await get_or_set_cache("some-key", mock_factory)
        assert val == "late-invalid-json"
        mock_factory.assert_not_called()


def test_versioned_key_builder() -> None:
    # Test key builder with request that has user and cache_version
    mock_request = MagicMock()
    mock_request.state.user.cache_version = 42

    # We mock default_key_builder to return "base-key"
    with patch(
        "fastapi_cache.key_builder.default_key_builder", return_value="base-key"
    ):
        res = versioned_key_builder(lambda: None, request=mock_request)
        assert res == "base-key:v42"
