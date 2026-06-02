from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.category import CategoryResponse


class TransactionType(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


# Reusable constrained types
PositiveAmount = Annotated[
    Decimal,
    Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Amount in the account currency",
    ),
]


class TransactionBase(BaseModel):
    """Shared fields across all transaction operations."""

    amount: PositiveAmount
    description: str = Field(min_length=1, max_length=500)
    date: Date
    category_id: int = Field(gt=0)
    transaction_type: TransactionType
    notes: str | None = Field(default=None, max_length=1000)
    tags: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Description cannot be empty")
        return v

    @field_validator("tags")
    @classmethod
    def normalise_tags(cls, v: list[str]) -> list[str]:
        """Deduplicate and lowercase tags."""
        return list({tag.lower().strip() for tag in v if tag.strip()})


class TransactionCreate(TransactionBase):
    """POST /transactions/ request body."""

    # user_id is NOT here — set from the authenticated user, never from client input
    pass


class TransactionUpdate(BaseModel):
    """
    PATCH /transactions/{id} — all fields optional.
    Does NOT inherit TransactionBase — every field must default to None
    so we can distinguish "client didn't send this field" from "client set it to None".
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    amount: PositiveAmount | None = None
    description: str | None = Field(default=None, min_length=1, max_length=500)
    date: Date | None = None
    category_id: int | None = Field(default=None, gt=0)
    notes: str | None = None
    tags: list[str] | None = None


class TransactionResponse(TransactionBase):
    """
    GET response for a single transaction or list items.
    Includes server-set fields and optionally the nested category.
    """

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    # category is optional here — some queries don't load the relationship
    # Use TransactionWithCategoryResponse when category is always loaded
    category: CategoryResponse | None = None


class TransactionWithCategoryResponse(TransactionBase):
    """
    GET response when category is always eagerly loaded.
    Use for single-item GET endpoints.
    """

    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
    )

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    # Required — not optional
    category: CategoryResponse


class TransactionFilters(BaseModel):
    """
    Query parameter group for filtering transactions.
    Used with Depends() in the list endpoint.

    All fields are optional — no filter applied when not provided.
    """

    date_from: Date | None = Field(default=None, description="Start date (inclusive)")
    date_to: Date | None = Field(default=None, description="End date (inclusive)")
    category_id: int | None = Field(default=None, gt=0)
    transaction_type: TransactionType | None = None
    min_amount: Decimal | None = Field(default=None, gt=0)
    max_amount: Decimal | None = Field(default=None, gt=0)
    search: str | None = Field(
        default=None, max_length=100, description="Search in description"
    )
    sort_by: Literal["date", "amount", "created_at"] = "date"
    sort_order: Literal["asc", "desc"] = "desc"

    @model_validator(mode="after")
    def validate_date_range(self) -> "TransactionFilters":
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("date_from must be before or equal to date_to")
        return self

    @model_validator(mode="after")
    def validate_amount_range(self) -> "TransactionFilters":
        if self.min_amount and self.max_amount and self.min_amount > self.max_amount:
            raise ValueError("min_amount must be less than or equal to max_amount")
        return self
