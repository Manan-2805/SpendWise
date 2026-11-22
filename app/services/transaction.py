from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccessDeniedError,
    CategoryNotFoundError,
    ConflictError,
    TransactionNotFoundError,
)
from app.models.category import Category
from app.models.transaction import Transaction
from app.repositories.category import CategoryRepository
from app.repositories.transaction import TransactionRepository
from app.schemas.transaction import (
    TransactionCreate,
    TransactionFilters,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.audit import AuditService
from app.services.report import mark_report_cache_dirty


class TransactionService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = TransactionRepository(db)
        self.category_repo = CategoryRepository(db)
        self.audit_service = AuditService(db)

    async def get_by_id_with_category(
        self, transaction_id: int, user_id: int
    ) -> TransactionResponse:
        transaction: Transaction | None = await self.repo.get_with_category(
            transaction_id, user_id
        )
        if not transaction:
            raise TransactionNotFoundError(transaction_id)
        return TransactionResponse.model_validate(transaction)

    async def get_filtered(
        self,
        user_id: int,
        filters: TransactionFilters,
        offset: int,
        limit: int,
    ) -> tuple[list[TransactionResponse], int]:
        transactions, total = await self.repo.get_filtered(
            user_id=user_id,
            date_from=filters.date_from,
            date_to=filters.date_to,
            category_id=filters.category_id,
            type=filters.type,
            min_amount=filters.min_amount,
            max_amount=filters.max_amount,
            search=filters.search,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
            skip=offset,
            limit=limit,
        )
        return [TransactionResponse.model_validate(t) for t in transactions], total

    async def _validate_category(
        self, category_id: int, user_id: int, tx_type: str
    ) -> None:
        category: Category | None = await self.category_repo.get_by_id(category_id)
        if not category:
            raise CategoryNotFoundError(category_id)
        if category.user_id != user_id and not category.is_shared:
            raise AccessDeniedError("Category does not belong to you")
        if category.type in {"income", "expense"} and category.type != tx_type:
            raise ConflictError("Transaction type conflicts with its category")

    async def create(
        self, data: TransactionCreate, user_id: int
    ) -> TransactionResponse:
        await mark_report_cache_dirty(self.db, user_id)
        await self._validate_category(data.category_id, user_id, data.type)

        transaction: Transaction = await self.repo.create(
            user_id=user_id,
            category_id=data.category_id,
            amount=data.amount,
            description=data.description,
            transaction_date=data.transaction_date,
            type=data.type,
            notes=data.notes,
            tags=data.tags,
        )

        await self.audit_service.log_action(
            action="TRANSACTION_CREATED",
            resource_type="Transaction",
            resource_id=transaction.id,
            user_id=user_id,
            new_values={
                "amount": str(data.amount),
                "category_id": data.category_id,
                "type": data.type,
            },
        )
        return TransactionResponse.model_validate(transaction)

    async def update(
        self, transaction_id: int, data: TransactionUpdate, user_id: int
    ) -> TransactionResponse:
        await mark_report_cache_dirty(self.db, user_id)
        existing: Transaction | None = await self.repo.get_by_id(transaction_id)
        if not existing:
            raise TransactionNotFoundError(transaction_id)
        if existing.user_id != user_id:
            raise AccessDeniedError()

        update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
        category_id = update_data.get("category_id", existing.category_id)
        if category_id is not None and (
            "category_id" in update_data or "type" in update_data
        ):
            await self._validate_category(
                category_id, user_id, data.type or existing.type
            )

        old_values = {
            "amount": str(existing.amount),
            "category_id": existing.category_id,
            "type": existing.type,
        }

        updated: Transaction | None = await self.repo.update(
            transaction_id, **update_data
        )

        await self.audit_service.log_action(
            action="TRANSACTION_UPDATED",
            resource_type="Transaction",
            resource_id=transaction_id,
            user_id=user_id,
            old_values=old_values,
            new_values=update_data,
        )
        return TransactionResponse.model_validate(updated)

    async def soft_delete(self, transaction_id: int, user_id: int) -> None:
        await mark_report_cache_dirty(self.db, user_id)
        transaction: Transaction | None = await self.repo.get_by_id(transaction_id)
        if not transaction:
            raise TransactionNotFoundError(transaction_id)
        if transaction.user_id != user_id:
            raise AccessDeniedError()

        await self.repo.soft_delete(transaction_id)
        await self.audit_service.log_action(
            action="TRANSACTION_DELETED",
            resource_type="Transaction",
            resource_id=transaction_id,
            user_id=user_id,
        )
