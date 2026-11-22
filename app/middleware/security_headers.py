from collections.abc import MutableMapping
from typing import Any

from starlette.types import ASGIApp, Receive, Scope, Send

from app.core.config import settings


class SecurityHeadersMiddleware:
    """
    Pure ASGI middleware that sets HSTS, CSP, X-Frame-Options,
    X-Content-Type-Options, Referrer-Policy, and Permissions-Policy headers.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message: MutableMapping[str, Any]) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))

                header_keys_to_set = {
                    b"x-frame-options": b"DENY",
                    b"x-content-type-options": b"nosniff",
                    b"referrer-policy": b"strict-origin-when-cross-origin",
                    b"content-security-policy": b"default-src 'self'",
                    b"permissions-policy": b"geolocation=(), microphone=(), camera=()",
                }

                path = scope.get("path", "")
                if settings.DEBUG and path in {"/docs", "/redoc"}:
                    header_keys_to_set[b"content-security-policy"] = (
                        b"default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
                        b"style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
                        b"font-src 'self' https://fonts.gstatic.com; img-src 'self' data: https://fastapi.tiangolo.com; "
                        b"worker-src 'self' blob:"
                    )

                if settings.ENVIRONMENT == "production":
                    header_keys_to_set[b"strict-transport-security"] = (
                        b"max-age=31536000; includeSubDomains"
                    )

                new_headers = []
                for k, v in headers:
                    if k.lower() not in header_keys_to_set:
                        new_headers.append((k, v))

                for k, v in header_keys_to_set.items():
                    new_headers.append((k, v))

                # Inject Cache-Control for Auth endpoints as per requirements
                auth_path = f"{settings.API_V1_PREFIX}/auth"
                if path == auth_path or path.startswith(f"{auth_path}/"):
                    new_headers = [
                        (k, v) for k, v in new_headers if k.lower() != b"cache-control"
                    ]
                    new_headers.append((b"cache-control", b"no-store, max-age=0"))

                message["headers"] = new_headers

            await send(message)

        await self.app(scope, receive, send_wrapper)
