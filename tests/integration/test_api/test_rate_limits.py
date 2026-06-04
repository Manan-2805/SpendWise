from unittest.mock import MagicMock, patch

from httpx import AsyncClient


async def test_rate_limit_exceeded_handler(client: AsyncClient) -> None:
    """Verify that custom rate limit handler formats 429 response correctly."""
    from slowapi.errors import RateLimitExceeded

    # Mock the rate limiter's check method to raise RateLimitExceeded immediately
    with patch("slowapi.Limiter._check_request_limit") as mock_check:
        mock_limit = MagicMock()
        mock_limit.limit = "5/minute"
        mock_check.side_effect = RateLimitExceeded(mock_limit)

        payload = {"email": "test@test.com", "password": "Password123!"}
        response = await client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 429

        data = response.json()
        assert data["code"] == "RATE_LIMIT_EXCEEDED"
        assert "Too many requests" in data["detail"]
