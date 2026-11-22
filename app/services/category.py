from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AccessDeniedError, CategoryNotFoundError, ConflictError
from app.models.category import Category
from app.repositories.category import CategoryRepository
from app.schemas.category import CategoryCreate, CategoryResponse, CategoryUpdate
from app.services.audit import AuditService
from app.services.report import mark_report_cache_dirty


class CategoryService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = CategoryRepository(db)
        self.audit_service = AuditService(db)

    async def get_all_for_user(
        self, user_id: int, offset: int = 0, limit: int = 100
    ) -> list[CategoryResponse]:
        categories: list[Category] = await self.repo.get_by_user_id(
            user_id, skip=offset, limit=limit
        )
        return [CategoryResponse.model_validate(c) for c in categories]

    async def get_by_id(self, category_id: int, user_id: int) -> CategoryResponse:
        category: Category | None = await self.repo.get_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id)
        if category.user_id != user_id and not category.is_shared:
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
        await mark_report_cache_dirty(self.db, user_id)
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

        if (
            data.type in {"income", "expense"}
            and data.type != category.type
            and await self.repo.has_active_transactions(
                category_id, user_id, incompatible_with=data.type
            )
        ):
            raise ConflictError("Category type conflicts with existing transactions")
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
        await mark_report_cache_dirty(self.db, user_id)
        category: Category | None = await self.repo.get_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id)
        if category.user_id != user_id:
            raise AccessDeniedError()

        if reassign_to_id == category_id:
            raise ConflictError("Choose a different target category")

        has_tx = await self.repo.has_active_transactions(category_id, user_id)
        if has_tx:
            if reassign_to_id is not None:
                target_cat = await self.repo.get_by_id(reassign_to_id)
                if not target_cat:
                    raise CategoryNotFoundError(reassign_to_id)
                if target_cat.user_id != user_id and not target_cat.is_shared:
                    raise AccessDeniedError("Target category does not belong to you")
                if target_cat.type in {
                    "income",
                    "expense",
                } and await self.repo.has_active_transactions(
                    category_id, user_id, incompatible_with=target_cat.type
                ):
                    raise ConflictError(
                        "Target category type conflicts with existing transactions"
                    )
                await self.repo.reassign_transactions(
                    category_id, reassign_to_id, user_id
                )
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
