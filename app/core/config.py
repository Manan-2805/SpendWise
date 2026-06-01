from functools import lru_cache
from typing import Literal

from pydantic import PostgresDsn, RedisDsn, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic-settings reads from:
    1. Environment variables (highest priority)
    2. .env file
    3. Default values defined here (lowest priority)

    Any missing variable without a default raises a ValidationError
    at startup — fail fast, never silently misconfigured.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,       # DATABASE_URL == database_url
        extra="ignore",             # Ignore env vars not defined here
    )

    # ─────────────────────────────────────────
    # Application
    # ─────────────────────────────────────────
    APP_NAME: str = "SpendWise"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = []

    # ─────────────────────────────────────────
    # Database
    # ─────────────────────────────────────────
    DATABASE_URL: PostgresDsn
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # ─────────────────────────────────────────
    # Redis
    # ─────────────────────────────────────────
    REDIS_URL: RedisDsn
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    # ─────────────────────────────────────────
    # Security — JWT
    # ─────────────────────────────────────────
    SECRET_KEY: str
    ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─────────────────────────────────────────
    # Google OAuth2
    # ─────────────────────────────────────────
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # ─────────────────────────────────────────
    # Email
    # ─────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAILS_FROM_EMAIL: str = "noreply@spendwise.local"
    EMAILS_FROM_NAME: str = "SpendWise"

    # ─────────────────────────────────────────
    # Computed fields — derived at initialisation
    # ─────────────────────────────────────────
    @computed_field  # type: ignore[misc]
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        Converts postgresql:// to postgresql+asyncpg://
        SQLAlchemy async requires the asyncpg driver prefix.
        """
        url = str(self.DATABASE_URL)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @computed_field  # type: ignore[misc]
    @property
    def GOOGLE_OAUTH_ENABLED(self) -> bool:
        """True only when both Google OAuth credentials are provided."""
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)

    # ─────────────────────────────────────────
    # Cross-field validation
    # ─────────────────────────────────────────
    @model_validator(mode="after")
    def validate_secret_key_strength(self) -> "Settings":
        """
        Enforce a minimum secret key length in production.
        A weak key in production is a critical security vulnerability.
        """
        if not self.DEBUG and len(self.SECRET_KEY) < 32:
            raise ValueError(
                "SECRET_KEY must be at least 32 characters in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return self

    @model_validator(mode="after")
    def validate_pool_configuration(self) -> "Settings":
        """Pool size + max overflow should not exceed database connection limits."""
        total = self.DATABASE_POOL_SIZE + self.DATABASE_MAX_OVERFLOW
        if total > 100:
            raise ValueError(
                f"DATABASE_POOL_SIZE ({self.DATABASE_POOL_SIZE}) + "
                f"DATABASE_MAX_OVERFLOW ({self.DATABASE_MAX_OVERFLOW}) = {total}. "
                "This exceeds typical PostgreSQL max_connections (100). "
                "Reduce pool sizes or increase PostgreSQL max_connections."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Return a cached Settings instance.

    @lru_cache ensures Settings() is called exactly once — the .env file
    is read once at startup, not on every request. This is the correct
    singleton pattern for configuration in Python.

    Usage:
        from app.core.config import get_settings
        settings = get_settings()

    In FastAPI dependencies:
        def get_current_settings(settings: Settings = Depends(get_settings)):
            return settings
    """
    return Settings()


# Module-level singleton — import this directly for convenience
# from app.core.config import settings
settings: Settings = get_settings()