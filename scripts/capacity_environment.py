"""Verify the disposable Compose target before a capacity tool can write."""

import json
import os
import re
import subprocess
from urllib.parse import urlsplit

import asyncpg

IDENTITY_SQL = "SELECT system_identifier::text FROM pg_catalog.pg_control_system()"
REFUSAL = "Refusing capacity operation outside the disposable capacity services."


def docker_output(*args: str) -> str:
    return subprocess.check_output(
        ["docker", *args], text=True, timeout=5, stderr=subprocess.DEVNULL
    ).strip()


def published_port(container: str, service: str, internal_port: str) -> int:
    if not re.fullmatch(r"[a-f0-9]{12,64}", container):
        raise ValueError("Missing capacity container ID")
    labels = json.loads(
        docker_output("inspect", "--format", "{{json .Config.Labels}}", container)
    )
    if (
        labels.get("com.spendwise.disposable") != "capacity"
        or labels.get("com.docker.compose.project") != os.environ["CAPACITY_PROJECT"]
        or labels.get("com.docker.compose.service") != f"capacity-{service}"
    ):
        raise ValueError("Wrong capacity container identity")
    ports = json.loads(
        docker_output(
            "inspect", "--format", "{{json .NetworkSettings.Ports}}", container
        )
    )
    (binding,) = ports[internal_port]
    if binding["HostIp"] != "127.0.0.1":
        raise ValueError("Capacity port must be published on loopback")
    return int(binding["HostPort"])


async def verify_capacity_environment() -> None:
    try:
        if not os.environ["CAPACITY_PROJECT"].startswith("spendwise-capacity-"):
            raise ValueError("Wrong capacity project")
        postgres = os.environ["CAPACITY_POSTGRES_ID"]
        db_url = os.environ["DATABASE_URL"]
        db = urlsplit(db_url)
        redis = urlsplit(os.environ["REDIS_URL"])
        if (
            db.scheme != "postgresql"
            or db.hostname != "127.0.0.1"
            or db.username != "spendwise_capacity"
            or db.path != "/spendwise_capacity"
            or db.query
            or db.fragment
            or db.port != published_port(postgres, "postgres", "5432/tcp")
            or redis.scheme != "redis"
            or redis.hostname != "127.0.0.1"
            or redis.path != "/0"
            or redis.query
            or redis.fragment
            or redis.port
            != published_port(os.environ["CAPACITY_REDIS_ID"], "redis", "6379/tcp")
        ):
            raise ValueError("Wrong capacity connection URL")
        expected = docker_output(
            "exec",
            postgres,
            "psql",
            "-XAt",
            "-U",
            "spendwise_capacity",
            "-d",
            "spendwise_capacity",
            "-c",
            IDENTITY_SQL,
        )
        connection = await asyncpg.connect(db_url, timeout=2, command_timeout=2)
        try:
            if await connection.fetchval(IDENTITY_SQL) != expected:
                raise ValueError("Wrong PostgreSQL cluster")
        finally:
            await connection.close(timeout=2)
    except (
        KeyError,
        TypeError,
        ValueError,
        OSError,
        TimeoutError,
        asyncpg.PostgresError,
        subprocess.SubprocessError,
    ):
        raise RuntimeError(REFUSAL) from None
