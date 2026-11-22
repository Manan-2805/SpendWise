import pytest
from httpx import AsyncClient


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
async def test_security_headers_docs(client: AsyncClient) -> None:
    response = await client.get("/docs")
    headers = response.headers
    assert headers.get("content-security-policy") is not None
    csp = headers["content-security-policy"]
    assert "unsafe-inline" in csp
    assert "https://cdn.jsdelivr.net" in csp


@pytest.mark.asyncio
async def test_security_headers_redoc(client: AsyncClient) -> None:
    response = await client.get("/redoc")
    headers = response.headers
    assert headers.get("content-security-policy") is not None
    csp = headers["content-security-policy"]
    assert "unsafe-inline" in csp
    assert "https://cdn.jsdelivr.net" in csp
