import threading
from datetime import UTC, datetime
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from eyes.contracts.target import ExecutionResult
from eyes.runner.config import origin


class SecretHeader(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    secret_ref: str = Field(min_length=1, max_length=120)


class HttpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    url: str
    request_mode: Literal["input", "envelope"] = "envelope"
    response_mode: Literal["output", "result"] = "output"
    output_pointer: str = ""
    operation_pointer: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    secret_headers: list[SecretHeader] = Field(default_factory=list)
    cancel_url: str | None = None
    reconcile_url: str | None = None
    poll_seconds: float = Field(default=1, ge=0.1, le=60)
    request_timeout_seconds: float = Field(default=30, ge=0.1, le=86400)
    max_response_bytes: int = Field(default=1024 * 1024, ge=1024, le=8 * 1024 * 1024)

    @model_validator(mode="after")
    def pointers(self):
        for pointer in [self.output_pointer, self.operation_pointer]:
            if pointer and not pointer.startswith("/"):
                raise ValueError("response pointers must use JSON Pointer syntax")
        if self.reconcile_url and not self.operation_pointer:
            raise ValueError("reconcile_url requires operation_pointer")
        return self


def pointer(value, path):
    for part in path.split("/")[1:] if path else []:
        key = part.replace("~1", "/").replace("~0", "~")
        value = value[int(key)] if isinstance(value, list) else value[key]
    return value


class HttpAdapter:
    def __init__(self, config, context, allowed_origins, capabilities):
        self.config = HttpConfig.model_validate(config)
        self.context = context
        self.allowed_origins = allowed_origins
        self._capabilities = capabilities
        self.operation_id = None
        self.cancelled = threading.Event()
        self.client = httpx.Client(follow_redirects=False, trust_env=False)

    def capabilities(self):
        return self._capabilities

    def prepare(self, request):
        if request.artifact_requirements:
            raise ValueError(
                "HTTP task adapter cannot collect files; use Python SDK or structured output"
            )
        for url in [self.config.url, self.config.cancel_url, self.config.reconcile_url]:
            if url and origin(url) not in self.allowed_origins:
                raise ValueError("HTTP origin is not allowed by local Runner configuration")
        capabilities = request.target.capabilities
        if set(capabilities.observation) != {"task"}:
            raise ValueError("the HTTP task adapter only supports task observation")
        if capabilities.cancellation and not self.config.cancel_url:
            raise ValueError("cancellation capability requires cancel_url")
        if capabilities.reconciliation and not self.config.reconcile_url:
            raise ValueError("reconciliation capability requires reconcile_url")
        for header in self.config.secret_headers:
            if header.secret_ref not in self.context.secrets:
                raise ValueError(f"missing secret reference for header {header.name}")
        reserved = {"traceparent", "idempotency-key", "x-eyes-attempt-id", "x-eyes-session-id"}
        if reserved & {
            key.lower()
            for key in [
                *self.config.headers,
                *(header.name for header in self.config.secret_headers),
            ]
        }:
            raise ValueError("identity and trace headers are controlled by Eyes")

    def _call(self, url, request, payload):
        headers = {
            **self.config.headers,
            **{
                header.name: str(self.context.secrets[header.secret_ref])
                for header in self.config.secret_headers
            },
            "traceparent": request.traceparent,
            "Idempotency-Key": request.idempotency_key,
            "X-Eyes-Attempt-Id": str(request.attempt_id),
            "X-Eyes-Session-Id": str(request.attempt_id),
        }
        remaining = max(0.1, (request.deadline - datetime.now(UTC)).total_seconds())
        timeout = min(remaining, self.config.request_timeout_seconds)
        with self.context.span("http.request", {"http.request.method": "POST"}):
            with self.client.stream(
                "POST", url, json=payload, headers=headers, timeout=timeout
            ) as response:
                chunks, size = [], 0
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > self.config.max_response_bytes:
                        raise ValueError("HTTP response exceeds configured byte limit")
                    chunks.append(chunk)
                if response.status_code >= 300:
                    raise ValueError(
                        f"target HTTP status {response.status_code}; remote effects unconfirmed"
                    )
                import json

                return response.status_code, json.loads(b"".join(chunks))

    def execute(self, request):
        payload = (
            request.input
            if self.config.request_mode == "input"
            else request.model_dump(mode="json")
        )
        status, body = self._call(self.config.url, request, payload)
        if self.config.operation_pointer:
            operation = pointer(body, self.config.operation_pointer)
            if operation is not None:
                self.operation_id = str(operation)
                self.context.remote_operation(self.operation_id)
        if status == 202:
            if not self.operation_id or not self.config.reconcile_url:
                return ExecutionResult(
                    status="unknown",
                    error="remote operation accepted without a usable reconciliation endpoint",
                    remote_operation_id=self.operation_id,
                    cleanup_status="pending",
                    evidence_status="sealed",
                    dropped_events=0,
                )
            while not self.cancelled.wait(self.config.poll_seconds):
                result = self.reconcile(request)
                if result is not None:
                    return result
            raise RuntimeError("remote execution polling stopped; result unconfirmed")
        return self._result(body)

    def _result(self, body):
        if self.config.response_mode == "result":
            result = ExecutionResult.model_validate(pointer(body, self.config.output_pointer))
        else:
            output = pointer(body, self.config.output_pointer)
            if not isinstance(output, dict):
                raise ValueError("HTTP output must be a JSON object")
            result = ExecutionResult(
                status="succeeded",
                output=output,
                cleanup_status="pending",
                evidence_status="sealed",
                dropped_events=0,
            )
        if self.operation_id:
            result.remote_operation_id = self.operation_id
        return result

    def cancel(self, request):
        self.cancelled.set()
        if not self.config.cancel_url:
            return False
        _, body = self._call(
            self.config.cancel_url,
            request,
            {
                "attempt_id": str(request.attempt_id),
                "idempotency_key": request.idempotency_key,
                "operation_id": self.operation_id,
            },
        )
        return isinstance(body, dict) and body.get("stopped_confirmed") is True

    def reconcile(self, request):
        if not self.config.reconcile_url or not self.operation_id:
            return None
        _, body = self._call(
            self.config.reconcile_url,
            request,
            {"attempt_id": str(request.attempt_id), "operation_id": self.operation_id},
        )
        if body.get("state") in {"queued", "running"}:
            return None
        result = ExecutionResult.model_validate(body.get("result", body))
        result.remote_operation_id = self.operation_id
        return result

    def cleanup(self, request):
        # Closing local sockets does not assert that a remote operation stopped.
        self.client.close()
