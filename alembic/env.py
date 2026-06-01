import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# ── Load app configuration ────────────────────────────────────
from app.core.config import settings

# ── Import the base and ALL models ───────────────────────────
# Alembic's autogenerate works by comparing the current database schema
# against the metadata of all models it knows about.
# If you don't import a model here, Alembic won't know about it and
# won't generate migrations for it.
from app.db.base import Base

# Import all models so they register themselves with Base.metadata
from app.models import user, category, transaction

# ── Alembic Config ────────────────────────────────────────────
config = context.config

# Set up Python logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the sqlalchemy.url from our Settings
# This is how we avoid storing secrets in alembic.ini
config.set_main_option("sqlalchemy.url", settings.ASYNC_DATABASE_URL)

# The target metadata — Alembic compares this against the DB
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations without a database connection.
    Generates SQL scripts instead of executing them.
    Useful for reviewing migrations before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Include object-level comparison for detecting column changes
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations with an async engine.
    Required because our SQLAlchemy engine uses asyncpg.
    """
    connectable = create_async_engine(
        settings.ASYNC_DATABASE_URL,
        poolclass=pool.NullPool,    # NullPool: no connection pooling during migrations
                                    # Each migration gets a fresh connection — safer
    )

    async with connectable.connect() as connection:
        # run_sync runs the synchronous migration code inside the async context
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for online migrations (the default mode)."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
