"""Rejects requests carrying a NUL character (U+0000) with a 422.

Postgres text columns can't store NUL, so letting one through ends in a DBAPIError
(500) on the first query that binds it. Checked once here instead of on every
string field: the query string, the path and the JSON body.
"""
import re

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_DETAIL = "NUL character (\\u0000) is not allowed"
# In a JSON body NUL can only appear as the escape `\u0000`; an even number of
# backslashes before it means the backslash itself is escaped (literal text).
_JSON_NUL = re.compile(rb"(?<!\\)(?:\\\\)*\\u0000")


def _has_nul(raw: bytes) -> bool:
    return b"\x00" in raw or b"%00" in raw


class RejectNulMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw_path = scope.get("raw_path") or scope["path"].encode()
        if _has_nul(scope.get("query_string", b"")) or _has_nul(raw_path) or "\x00" in scope["path"]:
            await self._reject(scope, receive, send)
            return

        body = b""
        more_body = True
        while more_body:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body += message.get("body", b"")
            more_body = message.get("more_body", False)

        if b"\x00" in body or _JSON_NUL.search(body):
            await self._reject(scope, receive, send)
            return

        replayed = False

        async def replay() -> Message:
            nonlocal replayed
            if not replayed:
                replayed = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)

    @staticmethod
    async def _reject(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"detail": _DETAIL}, status_code=422)(scope, receive, send)
