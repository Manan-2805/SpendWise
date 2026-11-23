from typing import Any, Literal

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import OverloadedError


class OverloadPayload(BaseModel):
    detail: str
    code: Literal["OVERLOADED"]
    request_id: str | None


OVERLOAD_RESPONSES: dict[int | str, dict[str, Any]] = {
    503: {
        "description": "The API is temporarily at capacity.",
        "model": OverloadPayload,
        "headers": {
            "Retry-After": {
                "description": "Seconds to wait before retrying.",
                "schema": {"type": "integer", "minimum": 1},
            },
        },
    },
}


def overload_response(request: Request) -> JSONResponse:
    error = OverloadedError()
    return JSONResponse(
        status_code=error.status_code,
        content={
            "detail": error.message,
            "code": error.code,
            "request_id": getattr(request.state, "correlation_id", None),
        },
        headers={"Retry-After": str(settings.OVERLOAD_RETRY_AFTER_SECONDS)},
    )
