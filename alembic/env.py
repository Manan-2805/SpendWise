import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import app.models  # noqa: F401
from alembic import context
from app.core.config import settings
from app.db.base import Base

# We read DATABASE_URL from Settings (which reads from .env).
# This is the ONLY correct way — never hardcode or use alembic.ini for secrets.
# Import the base and ALL models
# This is the step most tutorials get wrong or omit.
# Alembic's autogenerate works by comparing what is in Base.metadata
# against what is in the database. If a model is not imported here,
# it is invisible to autogenerate — no migration will be generated for it.
# Importing Base registers its metadata object with Alembic.
# Import every model module so the models register themselves with Base.metadata.
# The side effect of these imports is the registration.

# Alembic config object─
config = context.config

# Configure Python logging from alembic.ini settings
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override the database URL from our Settings singleton.
# alembic.ini has: sqlalchemy.url = (blank)
# We set it here at runtime — the Settings class reads from .env
config.set_main_option("sqlalchemy.url", settings.ASYNC_DATABASE_URL)

# The metadata object Alembic compares against the live database.
# All models registered to Base.metadata via the imports above.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Generate SQL without connecting to the database.

    Called when you run: alembic upgrade head --sql > migration.sql
    Produces a SQL script you can review or apply manually.
    Useful for:
    - DBAs who need to approve SQL before it runs
    - Air-gapped production environments
    - Generating SQL for copy-paste into a migration tool
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,  # Embed literal values instead of bind parameters
        dialect_opts={"paramstyle": "named"},
        compare_type=True,  # Detect column type changes
        compare_server_default=True,  # Detect server_default changes
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """
    The actual migration runner — called from the async context.

    This function is synchronous because SQLAlchemy's migration context
    (context.run_migrations()) is synchronous. We bridge async → sync
    using run_sync() in run_async_migrations().
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Include schema name if using PostgreSQL schemas other than "public"
        # include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    Run migrations using an async engine (required for asyncpg).

    Key decisions:
    1. NullPool — no connection pooling during migrations.
       Why: Migrations hold schema locks (CREATE TABLE, ALTER TABLE).
       A pooled connection could hold these locks longer than needed.
       NullPool ensures each migration gets a fresh connection that is
       closed immediately after, releasing locks promptly.

    2. run_sync() — bridges async to sync.
       Why: Alembic's migration context is synchronous. SQLAlchemy provides
       run_sync() to run synchronous code within an async connection.
       The sync code (do_run_migrations) gets a synchronous Connection facade.
    """
    connectable = create_async_engine(
        settings.ASYNC_DATABASE_URL,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Entry point for normal (online) migration runs."""
    asyncio.run(run_async_migrations())


# Dispatch to offline or online mode based on Alembic's invocation
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
