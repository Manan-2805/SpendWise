import redis.asyncio as redis

from app.core.config import settings

# We initialize the connection pool at the module level.
# Connections are established lazily on the first await.
redis_client: redis.Redis = redis.Redis.from_url(
    str(settings.REDIS_URL),
    encoding="utf-8",
    decode_responses=True,  # Automatically decode bytes to strings
    max_connections=50,  # Pool size per worker process
    socket_timeout=5.0,  # Fail fast if Redis is unresponsive
    socket_connect_timeout=5.0,
    retry_on_timeout=True,
    health_check_interval=30,  # Send PING every 30s to keep connections alive
)


async def ping_redis() -> bool:
    """Used by health checks to verify Redis connectivity."""
    try:
        # timeout not directly supported in async redis ping, rely on socket_timeout
        return bool(await redis_client.ping())
    except (redis.RedisError, TimeoutError, Exception):
        return False


async def close_redis() -> None:
    """Called during application shutdown (lifespan)."""
    await redis_client.aclose()
