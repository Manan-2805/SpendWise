from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.models.user import User
from app.schemas.report import (
    BalanceTrendResponse,
    CategoryBreakdownResponse,
    MonthlySummaryResponse,
)
from app.services.report import ReportService

router = APIRouter()


@router.get("/monthly-summary", response_model=MonthlySummaryResponse)
async def get_monthly_summary(
    year: int | None = None,
    month: int | None = None,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> MonthlySummaryResponse:
    """Get the monthly financial summary (income, expense, balance)."""
    now = datetime.now(UTC)
    q_year = year or now.year
    q_month = month or now.month

    report_service = ReportService(db)
    return await report_service.monthly_summary(current_user.id, q_year, q_month)


@router.get("/category-breakdown", response_model=list[CategoryBreakdownResponse])
async def get_category_breakdown(
    date_from: date | None = None,
    date_to: date | None = None,
    type: Literal["income", "expense"] = "expense",
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[CategoryBreakdownResponse]:
    """Get spending/income breakdown by category for a date range."""
    now_date = datetime.now(UTC).date()
    q_date_to = date_to or now_date
    q_date_from = date_from or (q_date_to - timedelta(days=30))

    report_service = ReportService(db)
    return await report_service.category_breakdown(
        current_user.id, q_date_from, q_date_to, type
    )


@router.get("/balance-trend", response_model=list[BalanceTrendResponse])
async def get_balance_trend(
    date_from: date | None = None,
    date_to: date | None = None,
    months: int = 12,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> list[BalanceTrendResponse]:
    """Get the monthly balance trend over a historical period."""
    now_date = datetime.now(UTC).date()
    q_date_to = date_to or now_date
    q_date_from = date_from or (q_date_to - timedelta(days=30 * months))

    report_service = ReportService(db)
    return await report_service.balance_trend(current_user.id, q_date_from, q_date_to)
