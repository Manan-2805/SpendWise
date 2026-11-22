import secrets

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def production_settings(*, debug: bool = False, key: str) -> Settings:
    return Settings(
        _env_file=None,
        ENVIRONMENT="production",
        DEBUG=debug,
        DATABASE_URL="postgresql://localhost/spendwise",
        REDIS_URL="redis://localhost/0",
        CELERY_BROKER_URL="redis://localhost/1",
        CELERY_RESULT_BACKEND="redis://localhost/2",
        SECRET_KEY=key,
    )


def test_production_rejects_debug() -> None:
    with pytest.raises(ValidationError, match="DEBUG"):
        production_settings(debug=True, key=secrets.token_hex(32))


def test_production_rejects_placeholder_key() -> None:
    with pytest.raises(ValidationError, match="SECRET_KEY"):
        production_settings(key="CHANGE_ME_" * 5)
