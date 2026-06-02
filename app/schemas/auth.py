import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class LoginRequest(BaseModel):
    """POST /auth/login request body."""

    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    """POST /auth/register request body."""

    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str

    @field_validator("username")
    @classmethod
    def username_lowercase(cls, v: str) -> str:
        return v.lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """
        Enforce password complexity.
        Must contain at least: one uppercase, one lowercase, one digit.
        """
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

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

    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)
    confirm_new_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v

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
    new_password: str = Field(min_length=8, max_length=128)
    confirm_new_password: str

    @model_validator(mode="after")
    def passwords_match(self) -> "ResetPasswordRequest":
        if self.new_password != self.confirm_new_password:
            raise ValueError("Passwords do not match")
        return self
