import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any, cast

import structlog
from fastapi import Request, Response

from app.core.redis import redis_client

logger = structlog.get_logger()


async def get_or_set_cache[T](
    key: str,
    factory: Callable[[], Awaitable[T]],
    ttl: int = 3600,
) -> T:
    cached_val = await redis_client.get(key)
    if cached_val is not None:
        try:
            return cast(T, json.loads(cached_val))
        except Exception:
            return cached_val  # type: ignore[return-value]

    lock_key: str = f"lock:{key}"
    acquired = False
    for _ in range(50):
        acquired = bool(await redis_client.set(lock_key, "1", nx=True, ex=5))
        if acquired:
            break
        await asyncio.sleep(0.1)

    if not acquired:
        logger.warning("cache_lock_acquisition_failed", key=key)
        return await factory()

    try:
        cached_val = await redis_client.get(key)
        if cached_val is not None:
            try:
                return cast(T, json.loads(cached_val))
            except Exception:
                return cached_val  # type: ignore[return-value]

        result = await factory()
        serialized: str = json.dumps(result, default=str)
        await redis_client.set(key, serialized, ex=ttl)
        return result
    finally:
        await redis_client.delete(lock_key)


def versioned_key_builder(
    func: Any,
    namespace: str = "",
    request: Request | None = None,
    response: Response | None = None,
    *args: Any,
    **kwargs: Any,
) -> str:
    from fastapi_cache.key_builder import default_key_builder

    base: str = default_key_builder(
        func,
        namespace,
        request=request,
        response=response,
        args=args,
        kwargs=kwargs,
    )
    if request:
        user: Any | None = getattr(request.state, "user", None)
        if user and hasattr(user, "cache_version"):
            return f"{base}:v{user.cache_version}"
    return base
