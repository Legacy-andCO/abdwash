"""Bound request memory before JSON parsing, including chunked HTTP bodies."""

from collections.abc import Awaitable, Callable
from typing import Any

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

MAX_REQUEST_BYTES = 3 * 1024 * 1024


class SecurityBoundaryMiddleware:
    def __init__(self, app: ASGIApp, rate_check: Callable[[Scope], Awaitable[None]]) -> None:
        self.app = app
        self.rate_check = rate_check

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        from app.domain.errors import DomainError

        try:
            await self.rate_check(scope)
        except DomainError as exc:
            await JSONResponse(
                {"code": exc.code, "message": exc.message},
                status_code=exc.status_code,
                headers={"Cache-Control": "no-store", "Retry-After": "60"},
            )(scope, receive, send)
            return
        headers = dict(scope["headers"])
        length = headers.get(b"content-length")
        if length is not None:
            try:
                size = int(length)
                if size < 0:
                    raise ValueError
            except ValueError:
                await JSONResponse({"code": "INVALID_CONTENT_LENGTH"}, status_code=400)(
                    scope, receive, send
                )
                return
            if size > MAX_REQUEST_BYTES:
                await self.too_large(scope, receive, send)
                return
        chunks: list[Message] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > MAX_REQUEST_BYTES:
                await self.too_large(scope, receive, send)
                return
            chunks.append(message)
            if not message.get("more_body", False):
                break
        index = 0

        async def bounded_receive() -> Any:
            nonlocal index
            if index < len(chunks):
                result = chunks[index]
                index += 1
                return result
            return await receive()

        await self.app(scope, bounded_receive, send)

    @staticmethod
    async def too_large(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse(
            {"code": "REQUEST_TOO_LARGE"}, status_code=413, headers={"Cache-Control": "no-store"}
        )(scope, receive, send)
