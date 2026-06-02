from app.core.config import Settings, get_settings
from app.main import app


def get_test_settings() -> Settings:
    return Settings(
        DATABASE_URL="postgresql+asyncpg://spendwise:spendwise_dev_password@spendwise_postgres:5432/spendwise_test",
        REDIS_URL="redis://spendwise_redis:6379/1",
        SECRET_KEY="2e8a551d6dd3ae3e4e2c461948784821ff3e4b8e6384747e680ea2569bd88f52",
        DEBUG=True,
    )


# In your test fixtures:
app.dependency_overrides[get_settings] = get_test_settings
