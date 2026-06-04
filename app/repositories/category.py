from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.category import Category
from app.models.transaction import Transaction
from app.repositories.base import BaseRepository


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Category, session)

    async def get_by_user_id(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> list[Category]:
        """Get all categories owned by a specific user or system categories."""
        stmt = (
            select(Category)
            .where(
                or_(Category.user_id == user_id, Category.is_system),
                Category.deleted_at.is_(None),
            )
            .order_by(Category.name)
            .offset(skip)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name_for_user(
        self, name: str, user_id: int | None
    ) -> Category | None:
        """Check if a category with the name exists for this user (or system categories)."""
        stmt = select(Category).where(
            Category.name.ilike(name),
            Category.deleted_at.is_(None),
            or_(Category.user_id == user_id, Category.is_system),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def count_by_user(self, user_id: int) -> int:
        """Count how many categories are available for a user (non-deleted)."""
        stmt = select(func.count(Category.id)).where(
            or_(Category.user_id == user_id, Category.is_system),
            Category.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def has_active_transactions(self, category_id: int) -> bool:
        """Check if there are any non-deleted transactions referencing this category."""
        stmt = select(func.count(Transaction.id)).where(
            Transaction.category_id == category_id,
            Transaction.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return bool(result.scalar_one() > 0)

    async def reassign_transactions(
        self, from_category_id: int, to_category_id: int
    ) -> None:
        """Reassign all transactions from one category to another."""
        stmt = (
            update(Transaction)
            .where(
                Transaction.category_id == from_category_id,
                Transaction.deleted_at.is_(None),
            )
            .values(category_id=to_category_id)
        )
        await self.session.execute(stmt)
