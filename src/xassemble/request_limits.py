"""Bound answer requests before JSON or multipart parsing."""

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .answers import MAX_ANSWER_BYTES


class AnswerRequestLimit:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        applies = (
            scope["type"] == "http"
            and scope.get("method") == "POST"
            and path.startswith("/document-sets/")
            and path.endswith(("/questionnaire/answer-import", "/questionnaire/evaluate", "/generate"))
        )
        if not applies:
            await self.app(scope, receive, send)
            return
        # Allow multipart framing overhead; the endpoint separately bounds the actual file.
        limit = MAX_ANSWER_BYTES + (64 * 1024 if path.endswith("/answer-import") else 0)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            if len(body) + len(chunk) > limit:
                await JSONResponse({"detail": "Answer request exceeds the size limit"}, 413)(
                    scope, receive, send
                )
                return
            body.extend(chunk)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
