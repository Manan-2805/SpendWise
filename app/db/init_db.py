"""
First-run database initialisation.

This module handles:
1. Creating the schema (only in development — production uses Alembic)
2. Seeding reference data that must exist before the app is usable

In production: Alembic migrations handle schema creation and changes.
In development: We can also use create_all() for a fast reset.
In tests: conftest.py creates the schema and drops it after each test run.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base
from app.db.session import engine

log = structlog.get_logger()


async def create_tables() -> None:
    """
    Create all tables defined in Base.metadata.

    WARNING: Use only in development. In production, use:
        alembic upgrade head

    create_all() cannot handle ALTER TABLE — it only creates missing tables.
    Alembic handles all schema evolution correctly.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("database_tables_created")


async def drop_tables() -> None:
    """
    Drop all tables. Used only in tests for a clean slate.
    NEVER call this in production.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    log.info("database_tables_dropped")


async def seed_default_categories(session: AsyncSession, user_id: int) -> None:
    """
    Create default categories for a new user.
    Called after user registration to give users a starting set.
    """
    from app.models.category import Category

    default_categories = [
        {"name": "Food & Dining", "icon": "🍽️", "color": "#FF6B6B"},
        {"name": "Housing", "icon": "🏠", "color": "#4ECDC4"},
        {"name": "Transportation", "icon": "🚗", "color": "#45B7D1"},
        {"name": "Healthcare", "icon": "🏥", "color": "#96CEB4"},
        {"name": "Entertainment", "icon": "🎬", "color": "#FFEAA7"},
        {"name": "Shopping", "icon": "🛍️", "color": "#DDA0DD"},
        {"name": "Utilities", "icon": "💡", "color": "#98D8C8"},
        {"name": "Salary", "icon": "💼", "color": "#77DD77"},
        {"name": "Freelance", "icon": "💻", "color": "#89CFF0"},
        {"name": "Other", "icon": "📦", "color": "#B0B0B0"},
    ]

    for cat_data in default_categories:
        category = Category(user_id=user_id, **cat_data)
        session.add(category)

    await session.flush()
    log.info(
        "default_categories_seeded", user_id=user_id, count=len(default_categories)
    )
