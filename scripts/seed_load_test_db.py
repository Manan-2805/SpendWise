# scripts/seed_load_test_db.py
"""
Volume database seeding script for SpendWise load testing.
Populates the database with:
- 100 users: loadtest_user_{i}@example.com (password: SecurePassword123!)
- 3 categories per user
- 10,100 transactions distributed across the users and categories (past 90 days)

Use `make seed-capacity` for 5,000 users, 20,000 categories, and 320,000
transactions on the local stack.
"""

import argparse
import asyncio
import random
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User

SEED_PASSWORD = "SecurePassword123!"


async def verify_capacity_counts(session: AsyncSession, user_count: int) -> None:
    users = select(User.id).where(
        User.username.startswith("capacity_user_", autoescape=True)
    )
    counts = (
        await session.scalar(select(func.count()).select_from(users.subquery())),
        await session.scalar(
            select(func.count())
            .select_from(Category)
            .where(Category.user_id.in_(users))
        ),
        await session.scalar(
            select(func.count())
            .select_from(Transaction)
            .where(
                Transaction.user_id.in_(users),
                Transaction.tags.contains(["seed-volume"]),
            )
        ),
    )
    expected = (user_count, user_count * 4, user_count * 64)
    if counts != expected:
        raise RuntimeError(
            f"Incomplete capacity dataset. Expected {expected}, found {counts}."
        )
    print(
        f"Verified capacity dataset: {counts[0]:,} users, {counts[1]:,} categories, {counts[2]:,} seeded transactions."
    )


async def seed_volume(*, capacity: bool = False, user_count: int | None = None) -> None:
    if settings.ENVIRONMENT != "development":
        raise RuntimeError("Seeding is available only in development mode")

    if user_count is None:
        user_count = 5_000 if capacity else 100
    prefix = "capacity_user_" if capacity else "loadtest_user_"
    transactions_per_user = 64 if capacity else 101
    rng = random.Random(42) if capacity else random.Random()

    print("--- Starting Load Test Database Seeding ---")

    # 1. Pre-calculate password hash to save substantial execution time
    print("Pre-calculating bcrypt password hash...")
    pass_hash = hash_password(SEED_PASSWORD)

    async with AsyncSessionLocal() as session:
        # Check if users already exist
        stmt = select(User.id).where(User.username.startswith(prefix, autoescape=True))
        res = await session.execute(stmt)
        existing_users = res.scalars().all()
        if existing_users:
            if capacity:
                await verify_capacity_counts(session, user_count)
            print("Load test users already exist. Seeding skipped.")
            return

        print(f"Generating {user_count:,} test users...")
        users_to_create = []
        for i in range(1, user_count + 1):
            users_to_create.append(
                User(
                    email=f"{prefix}{i}@example.com",
                    username=f"{prefix}{i}",
                    hashed_password=pass_hash,
                    is_active=True,
                    is_verified=True,
                )
            )

        session.add_all(users_to_create)
        await session.flush()  # Generate IDs

        # 3. Create categories for each user
        print("Generating categories per user...")
        cat_names = ["Food & Dining", "Rent & Housing", "Work Salary"]
        cat_types = ["expense", "expense", "income"]
        cat_colors = ["#FF5733", "#3357FF", "#2ECC71"]
        cat_icons = ["food", "home", "work"]
        if capacity:
            cat_names.append("Transportation")
            cat_types.append("expense")
            cat_colors.append("#F1C40F")
            cat_icons.append("car")

        categories_created = []
        for user in users_to_create:
            for idx, name in enumerate(cat_names):
                categories_created.append(
                    Category(
                        user_id=user.id,
                        name=name,
                        type=cat_types[idx],
                        color=cat_colors[idx],
                        icon=cat_icons[idx],
                        description=f"Load test category {name}",
                    )
                )

        session.add_all(categories_created)
        await session.flush()  # Generate IDs

        # Group categories by user_id for transaction creation
        user_categories: dict[int, list[Category]] = {}
        for cat in categories_created:
            user_categories.setdefault(cat.user_id, []).append(cat)

        transaction_count = user_count * transactions_per_user
        print(f"Generating {transaction_count:,} transactions...")
        transactions_data = []
        today = date.today()
        descriptions = [
            "Grocery shopping",
            "Gas station refill",
            "Weekend dinner",
            "Coffee shop",
            "Utility bill",
            "Netflix subscription",
            "Paycheck",
            "Freelance invoice",
            "Online retail purchase",
            "Gym membership",
        ]

        # Pre-seed transactions list to use bulk database insert
        for user in users_to_create:
            cats = user_categories.get(user.id, [])
            if not cats:
                continue

            # Standard transaction count per user
            for _ in range(transactions_per_user):
                cat = rng.choice(cats)
                t_type = cat.type
                amount = (
                    round(rng.uniform(10.0, 350.0), 2)
                    if t_type == "expense"
                    else round(rng.uniform(500.0, 3000.0), 2)
                )

                tx_date = today - timedelta(days=rng.randint(0, 90))
                desc = (
                    rng.choice(descriptions[:6])
                    if t_type == "expense"
                    else rng.choice(descriptions[6:8])
                )
                transactions_data.append(
                    {
                        "user_id": user.id,
                        "category_id": cat.id,
                        "amount": Decimal(str(amount)),
                        "type": t_type,
                        "transaction_date": tx_date,
                        "description": desc,
                        "notes": "Load test generated transaction",
                        "tags": ["seed-volume", t_type],
                    }
                )
            if len(transactions_data) >= 5_000:
                await session.execute(insert(Transaction), transactions_data)
                transactions_data.clear()

        if transactions_data:
            await session.execute(insert(Transaction), transactions_data)
        if capacity:
            await verify_capacity_counts(session, user_count)
        await session.commit()

        print(
            f"Successfully seeded {user_count:,} users, {len(categories_created):,} categories, and {transaction_count:,} transactions."
        )
        print("--- Seeding Completed Successfully ---")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capacity", action="store_true")
    asyncio.run(seed_volume(capacity=parser.parse_args().capacity))
