import asyncio
from unittest.mock import patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.api.deps import get_db
from app.core.security import verify_token
from app.main import app
from app.models.auth import RefreshToken
from app.models.user import User
from tests.conftest import TestAsyncSessionLocal


async def test_registration_is_visible_in_an_independent_session(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delitem(app.dependency_overrides, get_db)
    monkeypatch.setattr("app.api.deps.AsyncSessionLocal", TestAsyncSessionLocal)
    email = f"{uuid4().hex}@example.com"
    payload = {
        "email": email,
        "username": uuid4().hex,
        "password": "ExamplePass123!",
        "confirm_password": "ExamplePass123!",
    }

    with patch("app.worker.tasks.send_verification_email.apply_async"):
        response = await client.post("/api/v1/auth/register", json=payload)

    assert response.status_code == 201
    async with TestAsyncSessionLocal() as reader:
        persisted = await reader.scalar(select(User).where(User.email == email))
        assert persisted is not None


async def test_report_rejects_unsupported_month(
    client: AsyncClient, verified_user: User, auth_headers
) -> None:
    response = await client.get(
        "/api/v1/reports/monthly-summary",
        params={"year": 2026, "month": 13},
        headers=auth_headers(verified_user),
    )
    assert response.status_code == 422


async def test_cookie_write_rejects_foreign_origin(
    client: AsyncClient, verified_user: User, auth_headers
) -> None:
    access_token = auth_headers(verified_user)["Authorization"].split(" ", 1)[1]
    client.cookies.set("access_token", access_token)
    response = await client.patch(
        "/api/v1/users/me",
        headers={"Origin": "https://other.example"},
        json={"username": "changed_name"},
    )
    assert response.status_code == 403


async def test_concurrent_refresh_creates_one_successor_and_revokes_its_family(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delitem(app.dependency_overrides, get_db)
    monkeypatch.setattr("app.api.deps.AsyncSessionLocal", TestAsyncSessionLocal)
    identity = uuid4().hex
    registration = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"{identity}@example.com",
            "username": identity,
            "password": "ExamplePass123!",
            "confirm_password": "ExamplePass123!",
        },
    )
    assert registration.status_code == 201
    original = registration.cookies["refresh_token"]

    responses = await asyncio.gather(
        client.post("/api/v1/auth/refresh", json={"refresh_token": original}),
        client.post("/api/v1/auth/refresh", json={"refresh_token": original}),
    )
    assert sorted(response.status_code for response in responses) == [200, 401]

    user_id = int(verify_token(original, "refresh")["sub"])
    async with TestAsyncSessionLocal() as reader:
        tokens = list(
            await reader.scalars(
                select(RefreshToken).where(RefreshToken.user_id == user_id)
            )
        )
        assert len(tokens) == 2
        assert all(token.revoked_at for token in tokens)


async def test_report_reads_new_values_after_transaction_write(
    client: AsyncClient, verified_user: User, auth_headers
) -> None:
    headers = auth_headers(verified_user)
    report = "/api/v1/reports/monthly-summary?year=2026&month=11"
    first = await client.get(report, headers=headers)
    assert first.status_code == 200
    assert float(first.json()["expense"]) == 0

    category = await client.post(
        "/api/v1/categories/",
        headers=headers,
        json={"name": "Groceries", "type": "expense"},
    )
    assert category.status_code == 201
    transaction = await client.post(
        "/api/v1/transactions/",
        headers=headers,
        json={
            "category_id": category.json()["id"],
            "amount": "24.50",
            "description": "Groceries",
            "transaction_date": "2026-11-20",
            "type": "expense",
        },
    )
    assert transaction.status_code == 201
    fresh = await client.get(report, headers=headers)
    assert fresh.status_code == 200
    assert fresh.json()["expense"] == "24.50"
