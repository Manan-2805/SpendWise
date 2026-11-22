from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_refresh_token
from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with additional lookup methods."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email (case-insensitive, non-deleted)."""
        stmt = select(User).where(
            User.email == email.lower(), User.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get a user by username (case-insensitive, non-deleted)."""
        stmt = select(User).where(
            User.username == username.lower(), User.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_verification_token(self, token: str) -> User | None:
        """Get a user by verification token (non-deleted)."""
        stmt = (
            select(User)
            .where(
                User.verification_token == hash_refresh_token(token),
                User.deleted_at.is_(None),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_reset_token(self, token: str) -> User | None:
        """Get a user by password reset token (non-deleted)."""
        stmt = (
            select(User)
            .where(
                User.reset_password_token == hash_refresh_token(token),
                User.deleted_at.is_(None),
            )
            .with_for_update()
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update(self, id: int, **data: Any) -> User | None:
        """Update a user profile and automatically increment cache_version."""
        instance: User | None = await self.get_by_id(id)
        if not instance:
            return None
        instance.cache_version += 1
        for key, value in data.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance
