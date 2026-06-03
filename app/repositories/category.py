from sqlalchemy import Result, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Category, session)

    async def get_by_user_id(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> list[Category]:
        """Get all categories owned by a specific user."""
        stmt: Select[tuple[Category]] = (
            select(Category)
            .where(Category.user_id == user_id, Category.deleted_at.is_(None))
            .order_by(Category.name)
            .offset(skip)
            .limit(limit)
        )
        result: Result[tuple[Category]] = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name_for_user(self, user_id: int, name: str) -> Category | None:
        """Check if a user already has a category with the given name."""
        stmt: Select[tuple[Category]] = select(Category).where(
            Category.user_id == user_id,
            Category.name.ilike(name),
            Category.deleted_at.is_(None),
        )
        result: Result[tuple[Category]] = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_user(self, user_id: int) -> int:
        """Count how many categories a user has (non-deleted)."""
        stmt: Select[tuple[int]] = select(func.count(Category.id)).where(
            Category.user_id == user_id, Category.deleted_at.is_(None)
        )
        result: Result[tuple[int]] = await self.session.execute(stmt)
        return result.scalar_one()
