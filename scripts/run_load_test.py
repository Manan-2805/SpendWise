"""Measure transaction listings and cached reports against a disposable local API."""

import argparse
import asyncio
import json
import math
import os
import platform
import secrets
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import httpx


@dataclass
class Measurements:
    latencies: list[float] = field(default_factory=list)
    errors: int = 0

    def summary(self, seconds: float) -> dict[str, float | int | None]:
        latencies = sorted(self.latencies)
        p95 = latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None
        return {
            "requests": len(latencies),
            "errors": self.errors,
            "requests_per_second": round(len(latencies) / seconds, 2),
            "p95_ms": round(p95, 2) if p95 is not None else None,
        }


def benchmark_env() -> dict[str, str]:
    database_port = os.getenv("TEST_POSTGRES_PORT", "55432")
    redis_port = os.getenv("TEST_REDIS_PORT", "56379")
    redis = f"redis://127.0.0.1:{redis_port}"
    return os.environ | {
        "ENVIRONMENT": "development",
        "DEBUG": "false",
        "DATABASE_URL": (
            f"postgresql://spendwise_test:spendwise_test_local@127.0.0.1:{database_port}/spendwise_test"
        ),
        "REDIS_URL": f"{redis}/3",
        "CELERY_BROKER_URL": f"{redis}/4",
        "CELERY_RESULT_BACKEND": f"{redis}/5",
        "SECRET_KEY": secrets.token_hex(32),
        "RATE_LIMIT_DEFAULT": "1000000/minute",
        "RATE_LIMIT_REGISTER": "10000/minute",
        "SMTP_HOST": "",
    }


async def wait_for_api(client: httpx.AsyncClient, process: subprocess.Popen) -> None:
    for _ in range(100):
        if process.poll() is not None:
            break
        try:
            response = await client.get("/health")
            if response.is_success:
                return
        except httpx.TransportError:
            pass
        await asyncio.sleep(0.1)
    raise RuntimeError("Benchmark API failed to start")


async def create_scenario(client: httpx.AsyncClient, count: int) -> tuple[str, str]:
    identity = uuid4().hex
    password = f"Bench7!{secrets.token_hex(16)}"
    registration = await client.post(
        "/auth/register",
        json={
            "email": f"{identity}@example.com",
            "username": identity,
            "password": password,
            "confirm_password": password,
        },
    )
    registration.raise_for_status()
    client.headers["Authorization"] = f"Bearer {registration.json()['access_token']}"
    category = await client.post(
        "/categories/", json={"name": "Benchmark", "type": "expense"}
    )
    category.raise_for_status()
    today = datetime.now(UTC).date()
    for number in range(count):
        transaction = await client.post(
            "/transactions/",
            json={
                "amount": "10.00",
                "category_id": category.json()["id"],
                "description": f"Benchmark expense {number}",
                "transaction_date": today.isoformat(),
                "type": "expense",
            },
        )
        transaction.raise_for_status()

    reports = f"/reports/monthly-summary?year={today.year}&month={today.month}"
    warmup = await client.get(reports)
    warmup.raise_for_status()
    return "/transactions/?per_page=20", reports


async def measure(
    client: httpx.AsyncClient, routes: tuple[str, str], concurrency: int, seconds: float
) -> dict[str, dict[str, int | float | None]]:
    samples = {route: Measurements() for route in routes}
    start = perf_counter()
    end = start + seconds

    async def worker(index: int) -> None:
        while perf_counter() < end:
            route = routes[index % len(routes)]
            sample = samples[route]
            before = perf_counter()
            try:
                response = await client.get(route)
                sample.errors += int(not response.is_success)
            except httpx.TransportError:
                sample.errors += 1
            sample.latencies.append((perf_counter() - before) * 1000)
            index += 1

    await asyncio.gather(*(worker(index) for index in range(concurrency)))
    elapsed = perf_counter() - start
    total = Measurements(
        [value for sample in samples.values() for value in sample.latencies],
        sum(sample.errors for sample in samples.values()),
    )
    return {"combined": total.summary(elapsed)} | {
        route: sample.summary(elapsed) for route, sample in samples.items()
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=15)
    parser.add_argument("--concurrency", type=int, default=10)
    parser.add_argument("--transactions", type=int, default=100)
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    if min(args.seconds, args.concurrency, args.transactions) <= 0:
        parser.error("Duration, concurrency, and transaction count must be positive")

    env = benchmark_env()
    environment_bin = Path(sys.executable).parent
    subprocess.run(
        [environment_bin / "alembic", "upgrade", "head"], env=env, check=True
    )
    with subprocess.Popen(
        [
            environment_bin / "granian",
            "--interface",
            "asgi",
            "--host",
            "127.0.0.1",
            "--port",
            str(args.port),
            "--workers",
            "2",
            "--no-access-log",
            "app.main:app",
        ],
        env=env,
        stdout=subprocess.DEVNULL,
    ) as process:
        try:
            async with httpx.AsyncClient(
                base_url=f"http://127.0.0.1:{args.port}/api/v1", timeout=8
            ) as client:
                await wait_for_api(client, process)
                routes = await create_scenario(client, args.transactions)
                results = await measure(client, routes, args.concurrency, args.seconds)
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()

    print(
        json.dumps(
            {
                "system": f"{platform.system()} {platform.machine()}",
                "logical_cpus": os.cpu_count(),
                "server_workers": 2,
                "duration_seconds": args.seconds,
                "concurrency": args.concurrency,
                "seeded_transactions": args.transactions,
                "results": results,
            },
            indent=2,
        )
    )
    if results["combined"]["errors"] or not results["combined"]["requests"]:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
