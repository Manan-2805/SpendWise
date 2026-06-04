from unittest.mock import AsyncMock, patch

from redis.exceptions import RedisError

from app.core.redis import close_redis, ping_redis


async def test_redis_utils() -> None:
    # Test ping_redis success
    mock_ping_true = AsyncMock(return_value=True)
    with patch("app.core.redis.redis_client.ping", mock_ping_true):
        assert await ping_redis() is True

    # Test ping_redis failure
    mock_ping_fail = AsyncMock(side_effect=RedisError)
    with patch("app.core.redis.redis_client.ping", mock_ping_fail):
        assert await ping_redis() is False

    # Test close_redis
    with patch(
        "app.core.redis.redis_client.aclose", new_callable=AsyncMock
    ) as mock_aclose:
        await close_redis()
        mock_aclose.assert_called_once()
