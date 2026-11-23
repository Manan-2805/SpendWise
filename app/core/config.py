import json
from functools import lru_cache
from string import hexdigits
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        hide_input_in_errors=True,
    )

    APP_NAME: str = "SpendWise"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 5
    READINESS_INTERVAL_SECONDS: float = Field(default=2, gt=0)
    READINESS_TIMEOUT_SECONDS: float = Field(default=0.2, gt=0)
    READINESS_MAX_AGE_SECONDS: float = Field(default=6, gt=0)

    REDIS_URL: str
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str

    SECRET_KEY: str
    ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    GOOGLE_OAUTH_ENABLED: bool = False
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    FRONTEND_URL: str = "http://localhost:3000"
    CORS_ORIGINS: Annotated[list[str], NoDecode] = []
    TRUSTED_HOSTS: list[str] = []
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_STARTTLS: bool = True
    TRACING_CONSOLE: bool = False

    RATE_LIMIT_DEFAULT: str = "200/minute"
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "3/minute"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_origins(cls, origins: object) -> object:
        if isinstance(origins, str):
            try:
                return json.loads(origins)
            except json.JSONDecodeError:
                return [
                    origin.strip() for origin in origins.split(",") if origin.strip()
                ]
        return origins

    @computed_field  # type: ignore[prop-decorator]
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        url = str(self.DATABASE_URL)
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @computed_field  # type: ignore[prop-decorator]
    @property
    def async_database_url(self) -> str:
        return self.ASYNC_DATABASE_URL

    @model_validator(mode="after")
    def validate_secret_key_strength(self) -> "Settings":
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be disabled in production.")
            if "*" in self.CORS_ORIGINS or "*" in self.TRUSTED_HOSTS:
                raise ValueError("Production origins and hosts must be explicit.")
            if self.SMTP_HOST and not self.SMTP_STARTTLS:
                raise ValueError("SMTP_STARTTLS must be enabled in production.")
            key = self.SECRET_KEY
            if (
                len(key) != 64
                or any(char not in hexdigits for char in key)
                or len(set(key.lower())) < 8
            ):
                raise ValueError(
                    "SECRET_KEY must be a generated 32-byte hexadecimal key in production."
                )
            for name, value in (
                ("REDIS_URL", self.REDIS_URL),
                ("CELERY_BROKER_URL", self.CELERY_BROKER_URL),
                ("CELERY_RESULT_BACKEND", self.CELERY_RESULT_BACKEND),
            ):
                if not urlsplit(value).password:
                    raise ValueError(
                        f"{name} must require authentication in production."
                    )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings: Settings = get_settings()
