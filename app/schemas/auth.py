import re
from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


def bcrypt_length(password: str) -> str:
    if len(password.encode("utf-8")) > 72:
        raise ValueError("Password exceeds 72 UTF-8 bytes")
    return password


def strong_password(password: str) -> str:
    if not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit")
    return password


Password = Annotated[str, Field(min_length=1), AfterValidator(bcrypt_length)]
NewPassword = Annotated[
    str,
    Field(min_length=8),
    AfterValidator(bcrypt_length),
    AfterValidator(strong_password),
]


class LoginRequest(BaseModel):
    """POST /auth/login request body."""

    email: EmailStr
    password: Password


class RegisterRequest(BaseModel):
    """POST /auth/register request body."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: NewPassword
    confirm_password: str

    @field_validator("username")
    @classmethod
    def username_lowercase(cls, v: str) -> str:
        return v.lower()

    @model_validator(mode="after")
    def passwords_match(self) -> "RegisterRequest":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class TokenResponse(BaseModel):
    """POST /auth/login response — access token details."""

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Seconds until access token expires")


class RefreshRequest(BaseModel):
    """POST /auth/refresh request body (when not using HttpOnly cookies)."""

    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """POST /users/me/password request body."""

    current_password: Password
    new_password: NewPassword
    confirm_new_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "PasswordChangeRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("New passwords do not match")
        return self


class ForgotPasswordRequest(BaseModel):
    """POST /auth/forgot-password request body."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """POST /auth/reset-password request body."""

    token: str
    new_password: NewPassword
    confirm_new_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("Passwords do not match")
        return self
