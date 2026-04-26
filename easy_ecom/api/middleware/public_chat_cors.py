from __future__ import annotations

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


class PublicChatCorsMiddleware:
    """Route-scoped CORS for the public embeddable chat endpoint.

    The endpoint itself still validates the Origin against the tenant channel
    allow-list before doing any work. This middleware only lets browsers reach
    that endpoint without widening CORS for authenticated APIs.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not str(scope.get("path", "")).startswith("/ai/chat/public/"):
            await self.app(scope, receive, send)
            return

        headers = {key.decode("latin1").lower(): value.decode("latin1") for key, value in scope.get("headers", [])}
        origin = headers.get("origin", "")

        if scope.get("method") == "OPTIONS":
            await send(
                {
                    "type": "http.response.start",
                    "status": 204,
                    "headers": self._cors_headers(origin),
                }
            )
            await send({"type": "http.response.body", "body": b""})
            return

        async def send_with_cors(message: Message) -> None:
            if message["type"] == "http.response.start" and origin:
                mutable_headers = MutableHeaders(scope=message)
                mutable_headers["Access-Control-Allow-Origin"] = origin
                mutable_headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
                mutable_headers["Access-Control-Allow-Headers"] = "Content-Type"
                mutable_headers["Vary"] = "Origin"
            await send(message)

        await self.app(scope, receive, send_with_cors)

    def _cors_headers(self, origin: str) -> list[tuple[bytes, bytes]]:
        if not origin:
            return []
        return [
            (b"access-control-allow-origin", origin.encode("latin1")),
            (b"access-control-allow-methods", b"POST, OPTIONS"),
            (b"access-control-allow-headers", b"Content-Type"),
            (b"vary", b"Origin"),
        ]
