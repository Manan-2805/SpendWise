import asyncio
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User

SYSTEM_CATEGORIES = [
    {
        "name": "Housing",
        "type": "expense",
        "color": "#FF5733",
        "icon": "home",
        "description": "Rent, mortgage, or housing fees",
    },
    {
        "name": "Groceries",
        "type": "expense",
        "color": "#33FF57",
        "icon": "shopping-cart",
        "description": "Food and supermarket purchases",
    },
    {
        "name": "Transportation",
        "type": "expense",
        "color": "#3357FF",
        "icon": "car",
        "description": "Fuel, public transit, or vehicle maintenance",
    },
    {
        "name": "Utilities",
        "type": "expense",
        "color": "#F1C40F",
        "icon": "bolt",
        "description": "Electricity, gas, water, internet",
    },
    {
        "name": "Salary",
        "type": "income",
        "color": "#2ECC71",
        "icon": "dollar-sign",
        "description": "Primary monthly income",
    },
    {
        "name": "Investments",
        "type": "income",
        "color": "#9B59B6",
        "icon": "trending-up",
        "description": "Stocks, dividends, or interest income",
    },
]


async def seed() -> None:
    print("--- Seeding Database ---")
    async with AsyncSessionLocal() as session:
        print("Seeding system categories...")
        for cat_data in SYSTEM_CATEGORIES:
            stmt = select(Category).where(
                Category.name == cat_data["name"], Category.is_system
            )
            res = await session.execute(stmt)
            existing = res.scalar_one_or_none()
            if not existing:
                cat = Category(
                    name=cat_data["name"],
                    type=cat_data["type"],
                    color=cat_data["color"],
                    icon=cat_data["icon"],
                    description=cat_data["description"],
                    is_system=True,
                )
                session.add(cat)
                print(f"Created system category: {cat_data['name']}")
        await session.commit()

        print("Checking demo user...")
        demo_email = "demo@spendwise.com"
        stmt_user = select(User).where(User.email == demo_email)
        res_user = await session.execute(stmt_user)
        user = res_user.scalar_one_or_none()

        if not user:
            user = User(
                email=demo_email,
                username="demo",
                hashed_password=hash_password("Password123"),
                is_active=True,
                is_verified=True,
            )
            session.add(user)
            await session.flush()
            print("Demo user 'demo@spendwise.com' created (Password: Password123).")
        else:
            print("Demo user already exists.")

        stmt_tx = select(Transaction).where(Transaction.user_id == user.id)
        res_tx = await session.execute(stmt_tx)
        existing_tx = res_tx.scalars().first()

        if not existing_tx:
            print("Seeding mock transactions for demo user...")
            stmt_cats = select(Category).where(
                (Category.is_system) | (Category.user_id == user.id)
            )
            res_cats = await session.execute(stmt_cats)
            cats = {c.name: c.id for c in res_cats.scalars().all()}

            today = date.today()
            mock_txs = [
                Transaction(
                    user_id=user.id,
                    category_id=cats.get("Salary"),
                    amount=Decimal("3500.00"),
                    type="income",
                    transaction_date=today - timedelta(days=25),
                    description="Monthly paycheck",
                ),
                Transaction(
                    user_id=user.id,
                    category_id=cats.get("Housing"),
                    amount=Decimal("1200.00"),
                    type="expense",
                    transaction_date=today - timedelta(days=24),
                    description="Rent payment",
                ),
                Transaction(
                    user_id=user.id,
                    category_id=cats.get("Groceries"),
                    amount=Decimal("150.50"),
                    type="expense",
                    transaction_date=today - timedelta(days=20),
                    description="Weekly shopping",
                ),
                Transaction(
                    user_id=user.id,
                    category_id=cats.get("Groceries"),
                    amount=Decimal("89.20"),
                    type="expense",
                    transaction_date=today - timedelta(days=12),
                    description="Mid-week grocery run",
                ),
                Transaction(
                    user_id=user.id,
                    category_id=cats.get("Transportation"),
                    amount=Decimal("45.00"),
                    type="expense",
                    transaction_date=today - timedelta(days=15),
                    description="Gasoline",
                ),
                Transaction(
                    user_id=user.id,
                    category_id=cats.get("Utilities"),
                    amount=Decimal("125.00"),
                    type="expense",
                    transaction_date=today - timedelta(days=5),
                    description="Electricity bill",
                ),
                Transaction(
                    user_id=user.id,
                    category_id=cats.get("Groceries"),
                    amount=Decimal("65.40"),
                    type="expense",
                    transaction_date=today - timedelta(days=2),
                    description="Supermarket run",
                ),
            ]
            session.add_all(mock_txs)
            await session.commit()
            print("Successfully seeded 7 mock transactions.")
        else:
            print("Demo user already has transactions. Skipping transaction seed.")

        print("--- Seeding Complete ---")


if __name__ == "__main__":
    asyncio.run(seed())
