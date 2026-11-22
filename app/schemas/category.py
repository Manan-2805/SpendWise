from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.schemas.common import require_value

CategoryName = Annotated[
    str, Field(min_length=1, max_length=100, description="Category name")
]


CategoryColor = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]


class CategoryBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: CategoryName
    description: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(
        default=None, max_length=50, description="Icon identifier or emoji"
    )
    color: CategoryColor | None = None
    type: Literal["income", "expense", "both"]


class CategoryCreate(CategoryBase):
    """POST /categories/ request body."""

    pass


class CategoryUpdate(BaseModel):
    """PATCH /categories/{id} — all optional."""

    model_config = ConfigDict(str_strip_whitespace=True)

    name: Annotated[CategoryName | None, AfterValidator(require_value)] = None
    description: str | None = None
    icon: str | None = None
    color: CategoryColor | None = None
    type: Annotated[
        Literal["income", "expense", "both"] | None, AfterValidator(require_value)
    ] = None


class CategoryResponse(CategoryBase):
    """GET /categories/ and GET /categories/{id} response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    color: str | None = None
    user_id: int | None
    created_at: datetime
    updated_at: datetime
