from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

CategoryName = Annotated[
    str, Field(min_length=1, max_length=100, description="Category name")
]


class CategoryBase(BaseModel):
    name: CategoryName
    description: str | None = Field(default=None, max_length=500)
    icon: str | None = Field(
        default=None, max_length=50, description="Icon identifier or emoji"
    )
    color: str | None = Field(
        default=None,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color code e.g. '#FF5733'",
    )


class CategoryCreate(CategoryBase):
    """POST /categories/ request body."""

    pass


class CategoryUpdate(BaseModel):
    """PATCH /categories/{id} — all optional."""

    name: CategoryName | None = None
    description: str | None = None
    icon: str | None = None
    color: str | None = None


class CategoryResponse(CategoryBase):
    """GET /categories/ and GET /categories/{id} response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
