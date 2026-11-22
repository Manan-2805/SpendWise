# scripts/seed_load_test_db.py
"""
Volume database seeding script for SpendWise load testing.
Populates the database with:
- 100 users: loadtest_user_{i}@example.com (password: SecurePassword123!)
- 3 categories per user
- 10,100 transactions distributed across the users and categories (past 90 days)

Usage:
  $env:DATABASE_URL="postgresql://user:pass@localhost:5432/spendwise_loadtest"
  uv run python -B scripts/seed_load_test_db.py
"""

import asyncio
import random
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import insert, select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User


async def seed_volume() -> None:
    print("--- Starting Load Test Database Seeding ---")

    # 1. Pre-calculate password hash to save substantial execution time
    print("Pre-calculating bcrypt password hash...")
    pass_hash = hash_password("SecurePassword123!")

    async with AsyncSessionLocal() as session:
        # Check if users already exist
        stmt = select(User).where(User.email.like("loadtest_user_%@example.com"))
        res = await session.execute(stmt)
        existing_users = res.scalars().all()
        if existing_users:
            print("Load test users already exist. Seeding skipped.")
            return

        # 2. Bulk create 100 users
        print("Generating 100 test users...")
        users_to_create = []
        for i in range(1, 101):
            users_to_create.append(
                User(
                    email=f"loadtest_user_{i}@example.com",
                    username=f"loadtest_user_{i}",
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

        categories_created = []
        for user in users_to_create:
            for idx in range(3):
                categories_created.append(
                    Category(
                        user_id=user.id,
                        name=cat_names[idx],
                        type=cat_types[idx],
                        color=cat_colors[idx],
                        icon=cat_icons[idx],
                        description=f"Load test category {cat_names[idx]}",
                    )
                )

        session.add_all(categories_created)
        await session.flush()  # Generate IDs

        # Group categories by user_id for transaction creation
        user_categories: dict[int, list[Category]] = {}
        for cat in categories_created:
            user_categories.setdefault(cat.user_id, []).append(cat)

        # 4. Generate 10,100 transactions (approx 101 per user)
        print("Generating 10,100 transactions...")
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
            for _ in range(101):
                cat = random.choice(cats)
                t_type = cat.type
                amount = (
                    round(random.uniform(10.0, 350.0), 2)
                    if t_type == "expense"
                    else round(random.uniform(500.0, 3000.0), 2)
                )

                tx_date = today - timedelta(days=random.randint(0, 90))
                desc = (
                    random.choice(descriptions[:6])
                    if t_type == "expense"
                    else random.choice(descriptions[6:8])
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

        # Execute bulk insert for high performance
        print("Executing bulk database insert for transactions...")
        await session.execute(insert(Transaction), transactions_data)
        await session.commit()

        print(
            f"Successfully seeded 100 users, {len(categories_created)} categories, and {len(transactions_data)} transactions."
        )
        print("--- Seeding Completed Successfully ---")


if __name__ == "__main__":
    asyncio.run(seed_volume())
