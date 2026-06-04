import asyncio
import getpass
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def create_superuser() -> None:
    print("--- Create Superuser ---")
    email = input("Email: ").strip()
    username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm Password: ")

    if not email or not username or not password:
        print("Error: Email, username, and password are required.")
        sys.exit(1)

    if password != confirm:
        print("Error: Passwords do not match.")
        sys.exit(1)

    if len(password) < 8:
        print("Error: Password must be at least 8 characters long.")
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        stmt = select(User).where(User.email == email)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            print(f"Error: Email {email} is already registered.")
            sys.exit(1)

        stmt = select(User).where(User.username == username)
        res = await session.execute(stmt)
        if res.scalar_one_or_none():
            print(f"Error: Username {username} is already taken.")
            sys.exit(1)

        hashed = hash_password(password)
        user = User(
            email=email.lower(),
            username=username.lower(),
            hashed_password=hashed,
            is_active=True,
            is_verified=True,
            is_superuser=True,
        )
        session.add(user)
        await session.commit()
        print(f"Superuser {username} created successfully!")


if __name__ == "__main__":
    asyncio.run(create_superuser())
