import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.rate_limit import limiter
from app.main import create_application


@pytest.fixture(autouse=True)
def disable_rate_limiting(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limiter, "enabled", False)


@pytest.mark.asyncio
async def test_security_headers_default(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert headers.get("content-security-policy") == "default-src 'self'"


@pytest.mark.asyncio
async def test_security_headers_docs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DEBUG", True)
    async with AsyncClient(
        transport=ASGITransport(app=create_application()), base_url="http://test"
    ) as client:
        response = await client.get("/docs")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("content-security-policy") is not None
    csp = headers["content-security-policy"]
    assert "unsafe-inline" in csp
    assert "https://cdn.jsdelivr.net" in csp


@pytest.mark.asyncio
async def test_security_headers_redoc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DEBUG", True)
    async with AsyncClient(
        transport=ASGITransport(app=create_application()), base_url="http://test"
    ) as client:
        response = await client.get("/redoc")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("content-security-policy") is not None
    csp = headers["content-security-policy"]
    assert "unsafe-inline" in csp
    assert "https://cdn.jsdelivr.net" in csp
