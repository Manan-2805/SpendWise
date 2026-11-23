from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import OverloadedError


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
