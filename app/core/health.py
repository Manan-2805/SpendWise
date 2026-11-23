import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack, asynccontextmanager, suppress
from time import monotonic

from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings

Probe = Callable[[], Awaitable[bool]]
DependencyStatus = tuple[bool, bool, bool]
UNAVAILABLE: DependencyStatus = (False, False, False)


class Readiness:
    def __init__(
        self,
        db: Probe,
        redis: Probe,
        broker: Probe,
        *,
        interval: float,
        timeout: float,
        max_age: float,
    ) -> None:
        self.probes = (db, redis, broker)
        self.interval = interval
        self.timeout = timeout
        self.max_age = max_age
        self.updated_at = 0.0
        self.status = UNAVAILABLE

    def current(self) -> DependencyStatus:
        if monotonic() - self.updated_at >= self.max_age:
            return UNAVAILABLE
        return self.status

    async def refresh(self) -> None:
        async def check(probe: Probe) -> bool:
            try:
                async with asyncio.timeout(self.timeout):
                    return await probe()
            except Exception:
                return False

        db, redis, broker = await asyncio.gather(
            *(check(probe) for probe in self.probes)
        )
        self.status = (db, redis, broker)
        self.updated_at = monotonic()

    async def run(self) -> None:
        while True:
            await asyncio.sleep(self.interval)
            await self.refresh()


@asynccontextmanager
async def monitor_readiness() -> AsyncIterator[Readiness]:
    timeout = settings.READINESS_TIMEOUT_SECONDS
    async with AsyncExitStack() as stack:
        engine = create_async_engine(
            settings.ASYNC_DATABASE_URL,
            pool_size=1,
            max_overflow=0,
            pool_timeout=timeout,
            connect_args={"timeout": timeout, "command_timeout": timeout},
            hide_parameters=True,
        )
        stack.push_async_callback(engine.dispose)

        def redis_client(url: str) -> Redis:
            client = Redis.from_url(
                url,
                max_connections=1,
                socket_connect_timeout=timeout,
                socket_timeout=timeout,
                retry=Retry(NoBackoff(), 0),
            )
            stack.push_async_callback(client.aclose)
            return client

        cache = redis_client(settings.REDIS_URL)
        broker = redis_client(settings.CELERY_BROKER_URL)

        async def check_db() -> bool:
            async with engine.connect() as connection:
                return bool(await connection.scalar(text("SELECT 1")) == 1)

        async def check_cache() -> bool:
            return bool(await cache.ping())

        async def check_broker() -> bool:
            return bool(await broker.ping())

        monitor = Readiness(
            check_db,
            check_cache,
            check_broker,
            interval=settings.READINESS_INTERVAL_SECONDS,
            timeout=timeout,
            max_age=settings.READINESS_MAX_AGE_SECONDS,
        )
        await monitor.refresh()
        task = asyncio.create_task(monitor.run())
        try:
            yield monitor
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
