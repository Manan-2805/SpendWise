from datetime import date
from decimal import Decimal
from typing import Any, Literal

from sqlalchemy import and_, extract, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.category import Category
from app.models.transaction import Transaction
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Transaction, session)

    async def get_with_category(self, id: int, user_id: int) -> Transaction | None:
        """Get a transaction by ID with its category eagerly loaded, verifying ownership."""
        stmt = (
            select(Transaction)
            .options(
                joinedload(
                    Transaction.category.and_(
                        or_(
                            Category.user_id == user_id,
                            and_(Category.is_system, Category.user_id.is_(None)),
                        ),
                        Category.deleted_at.is_(None),
                    )
                )
            )
            .where(
                Transaction.id == id,
                Transaction.user_id == user_id,
                Transaction.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_filtered(
        self,
        user_id: int,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
        category_id: int | None = None,
        type: str | None = None,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        search: str | None = None,
        sort_by: str = "transaction_date",
        sort_order: Literal["asc", "desc"] = "desc",
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[list[Transaction], int]:
        """Advanced filtering and pagination for transactions, returning (items, total_count)."""
        conditions = [
            Transaction.user_id == user_id,
            Transaction.deleted_at.is_(None),
        ]

        if date_from:
            conditions.append(Transaction.transaction_date >= date_from)
        if date_to:
            conditions.append(Transaction.transaction_date <= date_to)
        if category_id is not None:
            conditions.append(Transaction.category_id == category_id)
        if type:
            conditions.append(Transaction.type == type)
        if min_amount is not None:
            conditions.append(Transaction.amount >= min_amount)
        if max_amount is not None:
            conditions.append(Transaction.amount <= max_amount)
        if search:
            conditions.append(
                Transaction.description.icontains(search, autoescape=True)
            )

        count_stmt = select(func.count(Transaction.id)).where(and_(*conditions))
        total_count = await self.session.scalar(count_stmt) or 0

        stmt = select(Transaction).where(and_(*conditions))

        allowed_sort_fields = {
            "transaction_date": Transaction.transaction_date,
            "date": Transaction.transaction_date,
            "amount": Transaction.amount,
            "description": Transaction.description,
            "created_at": Transaction.created_at,
        }
        sort_column = allowed_sort_fields.get(sort_by, Transaction.transaction_date)

        if sort_order == "desc":
            stmt = stmt.order_by(sort_column.desc(), Transaction.id.desc())
        else:
            stmt = stmt.order_by(sort_column.asc(), Transaction.id.asc())

        stmt = stmt.offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())

        return items, total_count

    async def get_monthly_summary(
        self, user_id: int, year: int, month: int
    ) -> dict[str, Decimal]:
        """Return total income and total expense for a specific month using index-friendly date filters."""
        start_date = date(year, month, 1)
        end_date: date = (
            date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
        )

        stmt = (
            select(
                Transaction.type,
                func.sum(Transaction.amount).label("total"),
            )
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.deleted_at.is_(None),
                    Transaction.transaction_date >= start_date,
                    Transaction.transaction_date < end_date,
                )
            )
            .group_by(Transaction.type)
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        summary = {"income": Decimal("0"), "expense": Decimal("0")}
        for row in rows:
            summary[row[0]] = row[1] or Decimal("0")
        return summary

    async def get_category_breakdown(
        self,
        user_id: int,
        date_from: date,
        date_to: date,
        type: str = "expense",
    ) -> list[dict[str, Any]]:
        """Category breakdown for a date range using JOIN + GROUP BY + window function."""
        stmt = (
            select(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                Category.color.label("category_color"),
                Category.icon.label("category_icon"),
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
                (
                    func.sum(Transaction.amount)
                    / func.sum(func.sum(Transaction.amount)).over()
                    * 100
                ).label("percentage"),
            )
            .outerjoin(
                Category,
                and_(
                    Transaction.category_id == Category.id,
                    Category.deleted_at.is_(None),
                    or_(
                        Category.user_id == user_id,
                        and_(Category.is_system, Category.user_id.is_(None)),
                    ),
                ),
            )
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.deleted_at.is_(None),
                    Transaction.type == type,
                    Transaction.transaction_date >= date_from,
                    Transaction.transaction_date <= date_to,
                )
            )
            .group_by(
                Category.id,
                Category.name,
                Category.color,
                Category.icon,
            )
            .order_by(func.sum(Transaction.amount).desc())
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "category_id": row.category_id,
                "category_name": row.category_name or "Uncategorized",
                "category_color": row.category_color,
                "category_icon": row.category_icon,
                "total": row.total,
                "count": row.count,
                "percentage": round(float(row.percentage or 0), 2),
            }
            for row in rows
        ]

    async def get_balance_trend(
        self, user_id: int, date_from: date, date_to: date
    ) -> list[dict[str, Any]]:
        """Monthly balance (income - expenses) for each month in the range."""
        from sqlalchemy import case as sql_case

        stmt = (
            select(
                extract("year", Transaction.transaction_date).label("year"),
                extract("month", Transaction.transaction_date).label("month"),
                func.sum(
                    sql_case(
                        (Transaction.type == "income", Transaction.amount),
                        else_=Decimal("0"),
                    )
                ).label("income"),
                func.sum(
                    sql_case(
                        (Transaction.type == "expense", Transaction.amount),
                        else_=Decimal("0"),
                    )
                ).label("expense"),
            )
            .where(
                and_(
                    Transaction.user_id == user_id,
                    Transaction.deleted_at.is_(None),
                    Transaction.transaction_date >= date_from,
                    Transaction.transaction_date <= date_to,
                )
            )
            .group_by(
                extract("year", Transaction.transaction_date),
                extract("month", Transaction.transaction_date),
            )
            .order_by(
                extract("year", Transaction.transaction_date),
                extract("month", Transaction.transaction_date),
            )
        )
        result = await self.session.execute(stmt)
        rows = result.all()
        return [
            {
                "year": int(row.year),
                "month": int(row.month),
                "income": row.income or Decimal("0"),
                "expense": row.expense or Decimal("0"),
                "balance": (row.income or Decimal("0")) - (row.expense or Decimal("0")),
            }
            for row in rows
        ]
