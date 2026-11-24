import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from typing import cast

import structlog
from redis.exceptions import RedisError

from app.core.redis import redis_client

logger = structlog.get_logger()

RELEASE_LOCK = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
    return redis.call('DEL', KEYS[1])
end
return 0
"""


async def get_or_set_cache[T](
    key: str,
    factory: Callable[[], Awaitable[T]],
    ttl: int = 3600,
) -> T:
    lock_key = f"{key}:lock"
    owner = uuid.uuid4().hex
    acquired = False
    try:
        for _ in range(5):
            cached = await redis_client.get(key)
            if cached is not None:
                try:
                    return cast(T, json.loads(cached))
                except (ValueError, TypeError):
                    logger.warning("invalid_cache_entry")
            acquired = bool(await redis_client.set(lock_key, owner, nx=True, ex=5))
            if acquired:
                break
            await asyncio.sleep(0.04)
    except RedisError:
        logger.warning("cache_read_failed")

    try:
        if acquired:
            try:
                cached = await redis_client.get(key)
                if cached is not None:
                    return cast(T, json.loads(cached))
            except (RedisError, ValueError, TypeError):
                logger.warning("cache_recheck_failed")
        result = await factory()
        if acquired:
            try:
                await redis_client.set(key, json.dumps(result, default=str), ex=ttl)
            except RedisError:
                logger.warning("cache_write_failed")
        return result
    finally:
        if acquired:
            try:
                await redis_client.eval(RELEASE_LOCK, 1, lock_key, owner)
            except RedisError:
                logger.warning("cache_lock_release_failed")
