from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_or_set_cache
from app.core.cache_keys import REPORT_CATEGORY, REPORT_MONTHLY, REPORT_TREND
from app.repositories.transaction import TransactionRepository
from app.schemas.report import (
    BalanceTrendResponse,
    CategoryBreakdownResponse,
    MonthlySummaryResponse,
)


class ReportService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = TransactionRepository(db)

    async def monthly_summary(
        self, user_id: int, year: int, month: int
    ) -> MonthlySummaryResponse:
        """Get monthly financial summary, cache-aside protected."""
        key = REPORT_MONTHLY.format(user_id=user_id, year=year, month=month)

        async def factory() -> dict[str, Any]:
            summary = await self.repo.get_monthly_summary(user_id, year, month)
            balance = summary["income"] - summary["expense"]
            return {
                "year": year,
                "month": month,
                "income": summary["income"],
                "expense": summary["expense"],
                "balance": balance,
            }

        data = await get_or_set_cache(key, factory, ttl=3600)
        return MonthlySummaryResponse.model_validate(data)

    async def category_breakdown(
        self,
        user_id: int,
        date_from: date,
        date_to: date,
        transaction_type: str = "expense",
    ) -> list[CategoryBreakdownResponse]:
        """Get financial breakdown by category for a date range, cache-aside protected."""
        key = REPORT_CATEGORY.format(
            user_id=user_id,
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
            transaction_type=transaction_type,
        )

        async def factory() -> list[dict[str, Any]]:
            return await self.repo.get_category_breakdown(
                user_id, date_from, date_to, transaction_type
            )

        data = await get_or_set_cache(key, factory, ttl=3600)
        return [CategoryBreakdownResponse.model_validate(item) for item in data]

    async def balance_trend(
        self, user_id: int, date_from: date, date_to: date
    ) -> list[BalanceTrendResponse]:
        """Get balance trend over time, cache-aside protected."""
        key = REPORT_TREND.format(
            user_id=user_id,
            date_from=date_from.isoformat(),
            date_to=date_to.isoformat(),
        )

        async def factory() -> list[dict[str, Any]]:
            return await self.repo.get_balance_trend(user_id, date_from, date_to)

        data = await get_or_set_cache(key, factory, ttl=3600)
        return [BalanceTrendResponse.model_validate(item) for item in data]
