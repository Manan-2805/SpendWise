from datetime import UTC, date, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.core.exceptions import BadRequestError
from app.models.user import User
from app.schemas.report import (
    BalanceTrendResponse,
    CategoryBreakdownResponse,
    MonthlySummaryResponse,
)
from app.services.report import ReportService

router = APIRouter()


def report_dates(
    date_from: date | None, date_to: date | None, today: date, default_days: int
) -> tuple[date, date]:
    end = date_to or today
    earliest = date(1900, 1, 1)
    latest = date(2100, 12, 31)
    if not earliest <= end <= latest:
        raise BadRequestError("date_to must be between 1900 and 2100")
    start = date_from or max(earliest, end - timedelta(days=default_days))
    if not earliest <= start <= end or (end - start).days > 366 * 5:
        raise BadRequestError("Use an ordered report range of up to five years")
    return start, end


@router.get("/monthly-summary", response_model=MonthlySummaryResponse)
async def get_monthly_summary(
    year: int | None = Query(default=None, ge=1900, le=2100),
    month: int | None = Query(default=None, ge=1, le=12),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db, scope="function"),
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
    db: AsyncSession = Depends(get_db, scope="function"),
) -> list[CategoryBreakdownResponse]:
    """Get spending/income breakdown by category for a date range."""
    now_date = datetime.now(UTC).date()
    q_date_from, q_date_to = report_dates(date_from, date_to, now_date, 30)

    report_service = ReportService(db)
    return await report_service.category_breakdown(
        current_user.id, q_date_from, q_date_to, type
    )


@router.get("/balance-trend", response_model=list[BalanceTrendResponse])
async def get_balance_trend(
    date_from: date | None = None,
    date_to: date | None = None,
    months: int = Query(default=12, ge=1, le=60),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db, scope="function"),
) -> list[BalanceTrendResponse]:
    """Get the monthly balance trend over a historical period."""
    now_date = datetime.now(UTC).date()
    q_date_from, q_date_to = report_dates(date_from, date_to, now_date, 30 * months)

    report_service = ReportService(db)
    return await report_service.balance_trend(current_user.id, q_date_from, q_date_to)
