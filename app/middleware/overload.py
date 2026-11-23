from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.api.responses import overload_response


class AdmissionMiddleware:
    def __init__(self, app: ASGIApp, *, limit: int, api_prefix: str) -> None:
        self.app = app
        self.limit = limit
        self.in_flight = 0
        self.exempt = {
            f"{api_prefix}/health",
            f"{api_prefix}/health/live",
            f"{api_prefix}/health/ready",
            "/metrics",
        }

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        root = scope.get("root_path", "")
        if root and path.startswith(f"{root}/"):
            path = path[len(root) :]
        if path in self.exempt:
            await self.app(scope, receive, send)
            return

        if self.in_flight >= self.limit:
            await overload_response(Request(scope))(scope, receive, send)
            return

        self.in_flight += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.in_flight -= 1
