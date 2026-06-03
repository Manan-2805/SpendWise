from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AccessDeniedError,
    CategoryNotFoundError,
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


class TransactionService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = TransactionRepository(db)
        self.category_repo = CategoryRepository(db)

    async def get_by_id_with_category(
        self, transaction_id: int, user_id: int
    ) -> TransactionResponse:
        transaction: Transaction | None = await self.repo.get_by_id_with_category(
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
    ) -> list[TransactionResponse]:
        transactions: list[Transaction] = await self.repo.get_filtered(
            user_id=user_id,
            date_from=filters.date_from,
            date_to=filters.date_to,
            category_id=filters.category_id,
            transaction_type=filters.transaction_type,
            min_amount=filters.min_amount,
            max_amount=filters.max_amount,
            search=filters.search,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
            skip=offset,
            limit=limit,
        )
        return [TransactionResponse.model_validate(t) for t in transactions]

    async def count_filtered(self, user_id: int, filters: TransactionFilters) -> int:
        return await self.repo.count_filtered(
            user_id=user_id,
            date_from=filters.date_from,
            date_to=filters.date_to,
            category_id=filters.category_id,
            transaction_type=filters.transaction_type,
            min_amount=filters.min_amount,
            max_amount=filters.max_amount,
            search=filters.search,
        )

    async def create(
        self, data: TransactionCreate, user_id: int
    ) -> TransactionResponse:
        # Validate category exists and belongs to user
        category: Category | None = await self.category_repo.get_by_id(data.category_id)
        if not category:
            raise CategoryNotFoundError(data.category_id)
        if category.user_id != user_id:
            raise AccessDeniedError("Category does not belong to you")

        transaction: Transaction = await self.repo.create(
            user_id=user_id,
            category_id=data.category_id,
            amount=data.amount,
            description=data.description,
            transaction_date=data.date,
            transaction_type=data.transaction_type,
            notes=data.notes,
            tags=data.tags,
        )
        return TransactionResponse.model_validate(transaction)

    async def update(
        self, transaction_id: int, data: TransactionUpdate, user_id: int
    ) -> TransactionResponse:
        # Verify transaction exists and belongs to user
        existing: Transaction | None = await self.repo.get_by_id(transaction_id)
        if not existing:
            raise TransactionNotFoundError(transaction_id)
        if existing.user_id != user_id:
            raise AccessDeniedError()

        # If category_id is being updated, validate the new category
        if data.category_id is not None:
            category: Category | None = await self.category_repo.get_by_id(
                data.category_id
            )
            if not category:
                raise CategoryNotFoundError(data.category_id)
            if category.user_id != user_id:
                raise AccessDeniedError("Category does not belong to you")

        update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
        # Convert schema field 'date' to model field 'transaction_date' if present
        if "date" in update_data:
            update_data["transaction_date"] = update_data.pop("date")

        updated: Transaction | None = await self.repo.update(
            transaction_id, **update_data
        )
        return TransactionResponse.model_validate(updated)

    async def soft_delete(self, transaction_id: int, user_id: int) -> None:
        transaction: Transaction | None = await self.repo.get_by_id(transaction_id)
        if not transaction:
            raise TransactionNotFoundError(transaction_id)
        if transaction.user_id != user_id:
            raise AccessDeniedError()
        await self.repo.soft_delete(transaction_id)
