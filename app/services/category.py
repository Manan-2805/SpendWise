from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccessDeniedError, CategoryNotFoundError, ConflictError
from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.audit import AuditService


class CategoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = CategoryRepository(db)
        self.audit_service = AuditService(db)

    async def get_all_for_user(self, user_id: int) -> list[CategoryResponse]:
        categories: list[Category] = await self.repo.get_by_user_id(user_id)
        return [CategoryResponse.model_validate(c) for c in categories]

    async def get_by_id(self, category_id: int, user_id: int) -> CategoryResponse:
        category: Category | None = await self.repo.get_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id)
        if category.user_id != user_id and not category.is_system:
            raise AccessDeniedError("This category does not belong to you")
        return CategoryResponse.model_validate(category)

    async def create(self, data: CategoryCreate, user_id: int) -> CategoryResponse:
        existing: Category | None = await self.repo.get_by_name_for_user(
            data.name, user_id
        )
        if existing:
            raise ConflictError(f"Category with name '{data.name}' already exists")

        category: Category = await self.repo.create(
            user_id=user_id,
            name=data.name,
            description=data.description,
            icon=data.icon,
            color=data.color,
            type=data.type,
        )
        await self.audit_service.log_action(
            action="CATEGORY_CREATED",
            resource_type="Category",
            resource_id=category.id,
            user_id=user_id,
        )
        return CategoryResponse.model_validate(category)

    async def update(
        self, category_id: int, data: CategoryUpdate, user_id: int
    ) -> CategoryResponse:
        category: Category | None = await self.repo.get_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id)
        if category.user_id != user_id:
            raise AccessDeniedError()

        if data.name:
            existing: Category | None = await self.repo.get_by_name_for_user(
                data.name, user_id
            )
            if existing and existing.id != category_id:
                raise ConflictError(f"Category with name '{data.name}' already exists")

        update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
        updated: Category | None = await self.repo.update(category_id, **update_data)
        await self.audit_service.log_action(
            action="CATEGORY_UPDATED",
            resource_type="Category",
            resource_id=category_id,
            user_id=user_id,
            new_values=update_data,
        )
        return CategoryResponse.model_validate(updated)

    async def soft_delete(
        self, category_id: int, user_id: int, reassign_to_id: int | None = None
    ) -> None:
        category: Category | None = await self.repo.get_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id)
        if category.user_id != user_id:
            raise AccessDeniedError()

        has_tx = await self.repo.has_active_transactions(category_id)
        if has_tx:
            if reassign_to_id is not None:
                target_cat = await self.repo.get_by_id(reassign_to_id)
                if not target_cat:
                    raise CategoryNotFoundError(reassign_to_id)
                if target_cat.user_id != user_id and not target_cat.is_system:
                    raise AccessDeniedError("Target category does not belong to you")
                await self.repo.reassign_transactions(category_id, reassign_to_id)
            else:
                raise ConflictError(
                    "Cannot delete category with active transactions. Reassign them first."
                )

        await self.repo.soft_delete(category_id)
        await self.audit_service.log_action(
            action="CATEGORY_DELETED",
            resource_type="Category",
            resource_id=category_id,
            user_id=user_id,
        )
