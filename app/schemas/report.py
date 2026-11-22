from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class MonthlySummaryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    income: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    expense: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    balance: Decimal = Field(default=Decimal("0.00"), decimal_places=2)


class CategoryBreakdownResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category_id: int | None
    category_name: str
    category_color: str | None = None
    category_icon: str | None = None
    total: Decimal = Field(..., decimal_places=2)
    count: int = Field(..., ge=0)
    percentage: float = Field(..., ge=0.0, le=100.0)


class BalanceTrendResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    year: int = Field(..., ge=1900, le=2100)
    month: int = Field(..., ge=1, le=12)
    income: Decimal = Field(..., decimal_places=2)
    expense: Decimal = Field(..., decimal_places=2)
    balance: Decimal = Field(..., decimal_places=2)
