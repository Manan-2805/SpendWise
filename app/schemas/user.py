from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

from app.schemas.common import require_value


class UserBase(BaseModel):
    """Shared user fields."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50)


class UserCreate(UserBase):
    """Used internally after RegisterRequest validation — includes hashed password."""

    hashed_password: str


class UserUpdate(BaseModel):
    """PATCH /users/me — all fields optional."""

    username: Annotated[
        str | None,
        Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"),
        AfterValidator(require_value),
    ] = None
    email: Annotated[EmailStr | None, AfterValidator(require_value)] = None


class UserResponse(UserBase):
    """GET /users/me response — safe public representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_verified: bool
    created_at: datetime

    # NOTE: hashed_password is NOT included here — never expose it
    # NOTE: deleted_at is NOT included — soft-deleted users should not be visible


class UserInDB(UserResponse):
    """
    Internal representation — includes DB-only fields.
    Used within the application layer, never sent directly to clients.
    """

    hashed_password: str
    updated_at: datetime
    deleted_at: datetime | None = None
