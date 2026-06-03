from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with additional lookup methods."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """Get a user by email (case-insensitive, non-deleted)."""
        stmt = select(User).where(User.email.ilike(email), User.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        """Get a user by username (case-insensitive, non-deleted)."""
        stmt = select(User).where(
            User.username.ilike(username), User.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_refresh_token_hash(
        self, user_id: int, token_hash: str | None
    ) -> None:
        """Store the hashed refresh token for a user."""
        user: User | None = await self.get_by_id(user_id)
        if user:
            user.refresh_token_hash = token_hash
            await self.session.flush()

    async def clear_refresh_token_hash(self, user_id: int) -> None:
        """Invalidate all refresh tokens for a user."""
        await self.update_refresh_token_hash(user_id, None)
