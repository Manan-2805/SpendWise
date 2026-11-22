# scripts/run_load_test.py
"""
Fully automated load testing and monitoring orchestrator.

This script:
1. Dynamically parses base connection details from `.env`.
2. Creates an isolated database named `spendwise_loadtest`.
3. Executes database migrations using Alembic.
4. Seeds 100 users and 10,000+ transactions into `spendwise_loadtest`.
5. Starts the Prometheus and Grafana Docker services.
6. Launches a temporary SpendWise API instance on port 8001.
7. Opens the system web browser directly to the Grafana Dashboard.
8. Runs the Locust load testing script in headless mode.
9. Performs full cleanup (kills the API, stops containers, drops the isolated DB).
"""

import argparse
import asyncio
import os
import subprocess
import sys
import time
import webbrowser
from urllib.parse import urlparse, urlunparse

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


def parse_db_urls(db_url: str) -> tuple[str, str]:
    """Parse connection URL to generate admin (postgres) and target (loadtest) URLs."""
    if db_url.startswith("postgresql+asyncpg://"):
        raw_url = db_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    else:
        raw_url = db_url

    parsed = urlparse(raw_url)
    admin_parsed = parsed._replace(path="/postgres")
    loadtest_parsed = parsed._replace(path="/spendwise_loadtest")

    admin_url = urlunparse(admin_parsed).replace("postgresql://", "postgresql+asyncpg://", 1)
    loadtest_url = urlunparse(loadtest_parsed).replace("postgresql://", "postgresql+asyncpg://", 1)

    return admin_url, loadtest_url


async def manage_loadtest_db(db_url: str, action: str) -> None:
    """Create or drop the isolated loadtest database."""
    admin_url, _ = parse_db_urls(db_url)
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")

    async with engine.connect() as conn:
        if action == "create":
            print("Creating isolated database 'spendwise_loadtest'...")
            await conn.execute(text("DROP DATABASE IF EXISTS spendwise_loadtest WITH (FORCE)"))
            await conn.execute(text("CREATE DATABASE spendwise_loadtest"))
        elif action == "drop":
            print("Dropping database 'spendwise_loadtest'...")
            await conn.execute(text("DROP DATABASE IF EXISTS spendwise_loadtest WITH (FORCE)"))

    await engine.dispose()


def run_command(command: list[str], env: dict[str, str] | None = None) -> None:
    """Synchronously run a system command and check for success."""
    result = subprocess.run(command, env=env, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Command {' '.join(command)} failed!")
        print(f"Error output:\n{result.stderr}")
        sys.exit(1)


async def main() -> None:
    # 1. Parse arguments
    parser = argparse.ArgumentParser(description="SpendWise Automated Load Tester")
    parser.add_argument("--users", type=int, default=100, help="Number of concurrent users")
    parser.add_argument("--rate", type=int, default=10, help="User spawn rate per second")
    parser.add_argument("--time", type=str, default="60s", help="Duration of the load test (e.g. 60s, 5m)")
    args = parser.parse_args()

    # Import config after parsing settings to read env variables correctly
    from app.core.config import settings

    db_url = settings.DATABASE_URL
    _, loadtest_url = parse_db_urls(db_url)

    # Convert loadtest asyncpg URL back to standard postgresql URL for Alembic & Docker env
    standard_loadtest_url = loadtest_url.replace("postgresql+asyncpg://", "postgresql://", 1)

    print("\n========================================================")
    print(" SpendWise Automated Load Test Pipeline Starting")
    print(f" Parameters: {args.users} users @ {args.rate}/s for {args.time}")
    print("========================================================\n")

    # 2. Database Lifecycle - Setup
    try:
        await manage_loadtest_db(db_url, "create")
    except Exception as e:
        print(f"Failed to create database: {e}")
        sys.exit(1)

    # 3. Database Schema - Migrations
    print("Running database migrations...")
    env = os.environ.copy()
    env["DATABASE_URL"] = standard_loadtest_url
    run_command(["uv", "run", "alembic", "upgrade", "head"], env=env)

    # 4. Database Seeding - Volume Data
    print("Seeding database with 10k+ transactions...")
    run_command(["uv", "run", "python", "-B", "scripts/seed_load_test_db.py"], env=env)

    # 5. Monitoring - Up
    print("Starting Prometheus and Grafana docker services...")
    run_command(["docker", "compose", "-f", "docker-compose.monitoring.yml", "up", "-d"])

    # 6. Start API server
    print("Starting SpendWise API server on port 8001...")
    api_env = env.copy()
    api_env["REDIS_URL"] = "redis://localhost:6379/1"
    api_env["CELERY_BROKER_URL"] = "redis://localhost:6379/1"
    api_env["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/1"
    api_env["RATE_LIMIT_LOGIN"] = "10000/minute"
    api_env["RATE_LIMIT_REGISTER"] = "10000/minute"
    api_env["ENVIRONMENT"] = "development"
    api_env["DEBUG"] = "True"

    # Start uvicorn as a background subprocess
    log_file = open("uvicorn_loadtest.log", "w", encoding="utf-8")
    api_process = subprocess.Popen(
        ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"],
        env=api_env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )

    # Wait for API server to become ready
    print("Waiting for API server to become responsive...")
    api_ready = False
    for _ in range(20):
        try:
            res = httpx.get("http://localhost:8001/api/v1/health", timeout=1.0)
            if res.status_code == 200:
                api_ready = True
                break
        except Exception:
            pass
        time.sleep(0.5)

    log_file.close()

    if not api_ready:
        print("Error: API server failed to start or did not become responsive.")
        if os.path.exists("uvicorn_loadtest.log"):
            with open("uvicorn_loadtest.log", encoding="utf-8") as f:
                print(f"\n--- API Server Log Output ---\n{f.read()}\n")
            try:
                os.remove("uvicorn_loadtest.log")
            except Exception:
                pass
        api_process.terminate()
        await manage_loadtest_db(db_url, "drop")
        sys.exit(1)

    try:
        os.remove("uvicorn_loadtest.log")
    except Exception:
        pass

    print("API server is healthy and responding.")

    # 7. Open Grafana Dashboard
    print("Opening Grafana dashboard in the system browser...")
    webbrowser.open("http://localhost:3000/datasources")

    # 8. Execute Locust Load Test
    print(f"Executing Locust load test headless against port 8001 for {args.time}...")
    locust_command = [
        "uv",
        "run",
        "locust",
        "-f",
        "tests/load/locustfile.py",
        "--headless",
        "--users",
        str(args.users),
        "--spawn-rate",
        str(args.rate),
        "--run-time",
        args.time,
        "--host",
        "http://localhost:8001",
        "--csv",
        "tests/load/results/locust_report",
    ]

    # Run locust and display real-time console output
    locust_process = subprocess.Popen(locust_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    # Stream output to console
    while True:
        line = locust_process.stdout.readline() if locust_process.stdout else ""
        if not line and locust_process.poll() is not None:
            break
        if line:
            print(line.strip())

    # 9. Cleanup
    print("\n========================================================")
    print(" Load Test Execution Finished — Commencing Cleanup")
    print("========================================================\n")

    print("Stopping API server...")
    api_process.terminate()
    api_process.wait()

    print("Stopping Prometheus and Grafana docker services...")
    run_command(["docker", "compose", "-f", "docker-compose.monitoring.yml", "down"])

    try:
        await manage_loadtest_db(db_url, "drop")
    except Exception as e:
        print(f"Failed to drop database: {e}")

    print("\nLoad test pipeline run completed successfully.")


if __name__ == "__main__":
    asyncio.run(main())
