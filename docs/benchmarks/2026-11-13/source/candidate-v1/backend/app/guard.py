"""Bound actual ASGI request bytes, including bodies without Content-Length."""

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse


class RequestGuard:
    def __init__(self, app, allow_insecure_local: bool = False, limit: int = 8192):
        self.app = app
        self.allow_insecure_local = allow_insecure_local
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def secure_send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Cache-Control"] = "no-store"
                headers["X-Content-Type-Options"] = "nosniff"
            await send(message)

        async def reject(detail, status):
            await JSONResponse({"detail": detail}, status)(scope, receive, secure_send)

        if scope["scheme"] != "https" and not self.allow_insecure_local:
            return await reject("HTTPS required. Configure trusted proxy TLS.", 400)
        lengths = Headers(scope=scope).getlist("content-length")
        if len(lengths) > 1 or any(
            not length.isascii()
            or not length.isdigit()
            or len(length) > 10
            or int(length) > self.limit
            for length in lengths
        ):
            return await reject("Request too large.", 413)

        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > self.limit:
                return await reject("Request too large.", 413)
            body.extend(chunk)
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, replay, secure_send)
