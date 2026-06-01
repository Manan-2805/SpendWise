#!/bin/bash
# docker/entrypoint.sh
# Runs before the main CMD — handles migrations and seeding

set -e    # Exit immediately on any error

echo "─────────────────────────────────────────────"
echo " SpendWise API Starting"
echo " Version: ${APP_VERSION:-unknown}"
echo "─────────────────────────────────────────────"

# Wait for the database to be ready
# The healthcheck in docker-compose handles this, but we add a fallback
echo "Waiting for database..."
python -c "
import asyncio
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    from app.core.config import settings
    engine = create_async_engine(settings.ASYNC_DATABASE_URL)
    for i in range(30):
        try:
            async with engine.connect() as conn:
                await conn.execute(text('SELECT 1'))
            print('Database is ready.')
            await engine.dispose()
            return
        except Exception:
            print(f'Attempt {i+1}/30 — database not ready yet...')
            await asyncio.sleep(2)
    print('Database did not become ready in time.')
    sys.exit(1)

asyncio.run(check())
"

# Run Alembic migrations
# Never skip this — it ensures the schema is always up to date
echo "Running database migrations..."
alembic upgrade head

# Optional: seed initial data (only in development or on first run)
if [ "${RUN_SEED:-false}" = "true" ]; then
    echo "Seeding database..."
    python scripts/seed_db.py
fi

echo "Starting application server..."

# exec replaces this shell process with the CMD
# This makes the CMD process PID 1, which is correct for signal handling
exec "$@"
