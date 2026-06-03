from typing import Any, Protocol

from sqlalchemy import Delete, Result, Select, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession


class RepositoryModel(Protocol):
    id: Any
    deleted_at: Any

    def soft_delete(self) -> None: ...


class BaseRepository[ModelType: RepositoryModel]:
    """
    Generic base repository providing standard CRUD operations.

    T must be a SQLAlchemy model class that inherits from Base.
    """

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model: type[ModelType] = model
        self.session: AsyncSession = session

    async def get_by_id(self, id: int) -> ModelType | None:
        """Get a single record by its primary key, respecting soft delete."""
        stmt: Select[tuple[ModelType]] = select(self.model).where(
            self.model.id == id, self.model.deleted_at.is_(None)
        )
        result: Result[tuple[ModelType]] = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        descending: bool = False,
    ) -> list[ModelType]:
        """
        Get multiple records with pagination and optional ordering.
        Only non-deleted records are returned.
        """
        stmt: Select[tuple[ModelType]] = select(self.model).where(
            self.model.deleted_at.is_(None)
        )
        if order_by and hasattr(self.model, order_by):
            order_col: Any = getattr(self.model, order_by)
            if descending:
                stmt = stmt.order_by(order_col.desc())
            else:
                stmt = stmt.order_by(order_col.asc())
        stmt = stmt.offset(skip).limit(limit)
        result: Result[tuple[ModelType]] = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self, **filters: Any) -> int:
        """Count total number of non-deleted records, optionally filtered."""
        query: Select[tuple[int]] = select(func.count(self.model.id)).where(
            self.model.deleted_at.is_(None)
        )
        for attr, value in filters.items():
            if hasattr(self.model, attr):
                query = query.where(getattr(self.model, attr) == value)
        result: Result[tuple[int]] = await self.session.execute(query)
        return result.scalar_one()

    async def create(self, **data: Any) -> ModelType:
        """Create a new record."""
        instance: ModelType = self.model(**data)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: int, **data: Any) -> ModelType | None:
        """
        Update a record by ID. Only non-deleted records are updated.
        Returns the updated instance or None if not found.
        """
        instance: ModelType | None = await self.get_by_id(id)
        if not instance:
            return None
        for key, value in data.items():
            if hasattr(instance, key) and value is not None:
                setattr(instance, key, value)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def soft_delete(self, id: int) -> bool:
        """
        Mark a record as deleted (soft delete). Returns True if deleted,
        False if record was already deleted or not found.
        """
        instance: ModelType | None = await self.get_by_id(id)
        if not instance or instance.deleted_at is not None:
            return False
        instance.soft_delete()
        await self.session.flush()
        return True

    async def hard_delete(self, id: int) -> bool:
        """
        Permanently delete a record from the database.
        Use with extreme caution — prefer soft_delete.
        """
        stmt: Delete = delete(self.model).where(
            self.model.id == id, self.model.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount > 0)  # type: ignore[attr-defined]
