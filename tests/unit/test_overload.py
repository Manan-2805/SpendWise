import asyncio

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.main import create_application


@pytest.mark.parametrize("exit_mode", ["response", "failure", "cancelled"])
async def test_admission_sheds_at_limit_and_releases_slot(exit_mode: str) -> None:
    from app.middleware.overload import AdmissionMiddleware

    api = FastAPI()
    started = asyncio.Event()
    leave = asyncio.Event()

    @api.get("/other/work")
    async def work(wait: bool = False):
        if wait:
            started.set()
            await leave.wait()
            if exit_mode == "failure":
                raise RuntimeError
        return {"status": "ok"}

    @api.get("/other/health")
    @api.get("/other/health/live")
    @api.get("/other/health/ready")
    async def health():
        return {"status": "ok"}

    app = AdmissionMiddleware(api, limit=1, api_prefix="/other")
    transport = ASGITransport(app=app, root_path="/proxy")
    async with (
        AsyncClient(
            transport=transport, base_url="http://test/proxy/other/"
        ) as existing,
        AsyncClient(transport=transport, base_url="http://test/proxy/other/") as other,
    ):
        held = asyncio.create_task(existing.get("work?wait=true"))
        try:
            await asyncio.wait_for(started.wait(), timeout=1)
            for health_path in ("health", "health/live", "health/ready"):
                assert (await other.get(health_path)).status_code == 200
            response = await asyncio.wait_for(other.get("work"), timeout=0.5)
            assert response.status_code == 503
            assert response.headers["retry-after"] == "1"
            assert response.json()["code"] == "OVERLOADED"
        finally:
            if exit_mode == "cancelled":
                held.cancel()
            leave.set()
            await asyncio.gather(held, return_exceptions=True)
        assert (await existing.get("work")).status_code == 200


def test_overload_response_is_in_openapi_for_api_routes() -> None:
    paths = create_application().openapi()["paths"]
    for path, method in (
        ("/auth/login", "post"),
        ("/users/me", "get"),
        ("/categories/", "post"),
        ("/transactions/", "get"),
        ("/reports/monthly-summary", "get"),
    ):
        response = paths[f"/api/v1{path}"][method]["responses"]["503"]
        assert response["headers"]["Retry-After"]["schema"]["type"] == "integer"
        assert response["content"]["application/json"]["schema"]
    assert "503" not in paths["/api/v1/health/live"]["get"]["responses"]
