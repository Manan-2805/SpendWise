from datetime import date as Date
from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.schemas.category import CategoryResponse
from app.schemas.common import require_value

PositiveAmount = Annotated[
    Decimal,
    Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Amount in the account currency",
    ),
]


def normalise_tags(tags: list[str]) -> list[str]:
    return list(dict.fromkeys(tag.strip().lower() for tag in tags if tag.strip()))


Description = Annotated[str, Field(min_length=1, max_length=500)]
Tag = Annotated[str, Field(max_length=64)]
Tags = Annotated[list[Tag], Field(max_length=10), AfterValidator(normalise_tags)]
Notes = Annotated[str, Field(max_length=1000)]


class TransactionBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    amount: PositiveAmount
    description: Description
    transaction_date: Date
    category_id: int = Field(gt=0)
    type: Literal["income", "expense"]
    notes: Notes | None = None
    tags: Tags = Field(default_factory=list)

    @field_validator("description")
    @classmethod
    def strip_description(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Description cannot be empty")
        return v


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    amount: Annotated[PositiveAmount | None, AfterValidator(require_value)] = None
    description: Annotated[Description | None, AfterValidator(require_value)] = None
    transaction_date: Annotated[Date | None, AfterValidator(require_value)] = None
    category_id: int | None = Field(default=None, gt=0)
    type: Annotated[
        Literal["income", "expense"] | None, AfterValidator(require_value)
    ] = None
    notes: Notes | None = None
    tags: Annotated[Tags | None, AfterValidator(require_value)] = None


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    amount: Decimal
    description: str | None
    transaction_date: Date
    category_id: int | None
    type: Literal["income", "expense"]
    notes: str | None
    tags: list[str]
    category: CategoryResponse | None = None


class TransactionWithCategoryResponse(TransactionResponse):
    pass


class TransactionFilters(BaseModel):
    date_from: Date | None = Field(default=None, description="Start date (inclusive)")
    date_to: Date | None = Field(default=None, description="End date (inclusive)")
    category_id: int | None = Field(default=None, gt=0)
    type: Literal["income", "expense"] | None = None
    min_amount: Decimal | None = Field(default=None, gt=0)
    max_amount: Decimal | None = Field(default=None, gt=0)
    search: str | None = Field(
        default=None, max_length=100, description="Search in description"
    )
    sort_by: Literal["transaction_date", "amount", "created_at"] = "transaction_date"
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
