from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import Result, Select, extract, func, select
from sqlalchemy.engine.row import Row
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute, joinedload

from app.models.transaction import Transaction
from app.repositories.base import BaseRepository
from app.schemas.transaction import TransactionType


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Transaction, session)

    async def get_by_id_with_category(
        self, id: int, user_id: int
    ) -> Transaction | None:
        """
        Get a transaction by ID with its category eagerly loaded.
        Also ensures the transaction belongs to the given user (security).
        """
        stmt: Select[tuple[Transaction]] = (
            select(Transaction)
            .options(joinedload(Transaction.category))
            .where(
                Transaction.id == id,
                Transaction.user_id == user_id,
                Transaction.deleted_at.is_(None),
            )
        )
        result: Result[tuple[Transaction]] = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_filtered(
        self,
        user_id: int,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        category_id: int | None = None,
        transaction_type: TransactionType | None = None,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        search: str | None = None,
        sort_by: str = "date",
        sort_order: Literal["asc", "desc"] = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> list[Transaction]:
        """
        Advanced filtering for transactions.
        Returns a list of transactions (without category loaded by default).
        """
        stmt: Select[tuple[Transaction]] = select(Transaction).where(
            Transaction.user_id == user_id, Transaction.deleted_at.is_(None)
        )

        # Apply filters
        if date_from:
            stmt = stmt.where(Transaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.where(Transaction.transaction_date <= date_to)
        if category_id is not None:
            stmt = stmt.where(Transaction.category_id == category_id)
        if transaction_type:
            stmt = stmt.where(Transaction.transaction_type == transaction_type)
        if min_amount is not None:
            stmt = stmt.where(Transaction.amount >= min_amount)
        if max_amount is not None:
            stmt = stmt.where(Transaction.amount <= max_amount)
        if search:
            stmt = stmt.where(Transaction.description.ilike(f"%{search}%"))

        # Apply sorting
        sort_column: Any | InstrumentedAttribute[date] = getattr(
            Transaction, sort_by, Transaction.transaction_date
        )
        if sort_order == "desc":
            stmt = stmt.order_by(sort_column.desc())
        else:
            stmt = stmt.order_by(sort_column.asc())

        stmt = stmt.offset(skip).limit(limit)
        result: Result[tuple[Transaction]] = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_filtered(
        self,
        user_id: int,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        category_id: int | None = None,
        transaction_type: TransactionType | None = None,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        search: str | None = None,
    ) -> int:
        """Count transactions matching the same filters as get_filtered."""
        stmt: Select[tuple[int]] = select(func.count(Transaction.id)).where(
            Transaction.user_id == user_id, Transaction.deleted_at.is_(None)
        )
        if date_from:
            stmt = stmt.where(Transaction.transaction_date >= date_from)
        if date_to:
            stmt = stmt.where(Transaction.transaction_date <= date_to)
        if category_id is not None:
            stmt = stmt.where(Transaction.category_id == category_id)
        if transaction_type:
            stmt = stmt.where(Transaction.transaction_type == transaction_type)
        if min_amount is not None:
            stmt = stmt.where(Transaction.amount >= min_amount)
        if max_amount is not None:
            stmt = stmt.where(Transaction.amount <= max_amount)
        if search:
            stmt = stmt.where(Transaction.description.ilike(f"%{search}%"))
        result: Result[tuple[int]] = await self.session.execute(stmt)
        return result.scalar_one()

    async def get_monthly_summary(
        self, user_id: int, year: int, month: int
    ) -> dict[str, Decimal]:
        """
        Return total income and total expense for a specific month.
        """
        stmt: Select[tuple[str, Decimal]] = (
            select(
                Transaction.transaction_type,
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                Transaction.user_id == user_id,
                Transaction.deleted_at.is_(None),
                extract("year", Transaction.transaction_date) == year,
                extract("month", Transaction.transaction_date) == month,
            )
            .group_by(Transaction.transaction_type)
        )
        result: Result[tuple[str, Decimal]] = await self.session.execute(stmt)
        rows: Sequence[Row[tuple[str, Decimal]]] = result.all()
        summary: dict[str, Decimal] = {"income": Decimal("0"), "expense": Decimal("0")}
        for row in rows:
            summary[row.transaction_type] = row.total or Decimal("0")
        return summary
