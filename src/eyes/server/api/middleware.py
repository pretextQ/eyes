import json

from opentelemetry import trace
from opentelemetry.propagate import extract
from starlette.responses import JSONResponse


class RequestBoundary:
    def __init__(self, app, settings, tracer):
        self.app = app
        self.settings = settings
        self.tracer = tracer

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        artifact = scope["method"] == "PUT" and scope["path"].startswith("/v1/artifacts/")
        limit = self.settings.max_artifact_bytes if artifact else self.settings.max_request_bytes
        headers = {
            key.decode("latin-1"): value.decode("latin-1") for key, value in scope["headers"]
        }
        size = 0
        parts = []
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > limit:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "schema_version": "1.0",
                        "error": {
                            "code": "payload_too_large",
                            "message": "request exceeds configured byte limit",
                        },
                    },
                )
                await response(scope, receive, send)
                return
            parts.append(message.get("body", b""))
            if not message.get("more_body", False):
                break
        body = b"".join(parts)
        sent_body = False

        async def replay():
            nonlocal sent_body
            if not sent_body:
                sent_body = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        with self.tracer.start_as_current_span(
            "eyes.api.request",
            context=extract(headers),
            kind=trace.SpanKind.SERVER,
            attributes={"http.request.method": scope["method"]},
        ) as span:

            async def traced_send(message):
                if message["type"] == "http.response.start":
                    span.set_attribute("http.response.status_code", message["status"])
                    if message["status"] >= 500:
                        span.set_status(trace.StatusCode.ERROR)
                    message["headers"] = [
                        *message["headers"],
                        (b"x-eyes-trace-id", f"{span.get_span_context().trace_id:032x}".encode()),
                    ]
                    route = scope.get("route")
                    if route is not None:
                        span.set_attribute("http.route", route.path)
                await send(message)

            await self.app(scope, replay, traced_send)


def validation_details(errors):
    # Pydantic error input/context can contain tokens or arbitrary submitted data.
    return json.loads(
        json.dumps(
            [{"type": item["type"], "loc": item["loc"], "msg": item["msg"]} for item in errors],
            default=str,
        )
    )
