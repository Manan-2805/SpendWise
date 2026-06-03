from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccessDeniedError,
    CategoryNotFoundError,
    ConflictError,
)
from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate


class CategoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = CategoryRepository(db)

    async def get_all_for_user(self, user_id: int) -> list[CategoryResponse]:
        categories: list[Category] = await self.repo.get_by_user_id(user_id)
        return [CategoryResponse.model_validate(c) for c in categories]

    async def get_by_id(self, category_id: int, user_id: int) -> CategoryResponse:
        category: Category | None = await self.repo.get_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id)
        if category.user_id != user_id:
            raise AccessDeniedError("This category does not belong to you")
        return CategoryResponse.model_validate(category)

    async def create(self, data: CategoryCreate, user_id: int) -> CategoryResponse:
        # Check duplicate name for this user
        existing: Category | None = await self.repo.get_by_name_for_user(
            user_id, data.name
        )
        if existing:
            raise ConflictError(f"Category with name '{data.name}' already exists")

        category: Category = await self.repo.create(
            user_id=user_id,
            name=data.name,
            description=data.description,
            icon=data.icon,
            color=data.color,
        )
        return CategoryResponse.model_validate(category)

    async def update(
        self, category_id: int, data: CategoryUpdate, user_id: int
    ) -> CategoryResponse:
        # Verify ownership
        category: Category | None = await self.repo.get_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id)
        if category.user_id != user_id:
            raise AccessDeniedError()

        # If name is being changed, check uniqueness
        if data.name:
            existing: Category | None = await self.repo.get_by_name_for_user(
                user_id, data.name
            )
            if existing and existing.id != category_id:
                raise ConflictError(f"Category with name '{data.name}' already exists")

        update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
        updated: Category | None = await self.repo.update(category_id, **update_data)
        return CategoryResponse.model_validate(updated)

    async def soft_delete(self, category_id: int, user_id: int) -> None:
        category: Category | None = await self.repo.get_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id)
        if category.user_id != user_id:
            raise AccessDeniedError()
        # Optionally check if category has transactions and prevent deletion
        # (Business decision: either allow with reassign or restrict)
        # For now, we allow soft delete but transactions will keep category_id.
        await self.repo.soft_delete(category_id)
