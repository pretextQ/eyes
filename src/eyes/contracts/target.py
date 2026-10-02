from datetime import datetime
from typing import Literal, Protocol
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import Field, model_validator

from eyes.contracts.base import Contract, Payload


def http_origin(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("URL must be HTTP(S), without embedded credentials")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    hostname = parsed.hostname.lower()
    if ":" in hostname:
        hostname = f"[{hostname}]"
    return f"{parsed.scheme}://{hostname}:{port}"


class TargetCapabilities(Contract):
    adapter: str = Field(min_length=1, max_length=120)
    session_isolation: bool
    environment_isolation: bool
    cancellation: bool = False
    idempotency: bool = False
    reconciliation: bool = False
    observation: list[Literal["task", "sdk", "target_trace"]] = Field(min_length=1)


class TargetPublish(Contract):
    name: str = Field(min_length=1, max_length=200)
    external_version: str | None = Field(default=None, max_length=200)
    capabilities: TargetCapabilities
    config: Payload = Field(default_factory=dict)
    secret_refs: dict[str, str] = Field(default_factory=dict)
    concurrency_limit: int = Field(default=1, ge=1, le=1000)

    @model_validator(mode="after")
    def check_isolation(self):
        if self.concurrency_limit > 1 and not (
            self.capabilities.session_isolation and self.capabilities.environment_isolation
        ):
            raise ValueError("concurrency > 1 requires session and environment isolation")
        return self


class ExecutionInput(Contract):
    experiment_id: UUID
    case_run_id: UUID
    attempt_id: UUID
    idempotency_key: str
    deadline: datetime
    traceparent: str = Field(pattern=r"^00-[0-9a-f]{32}-[0-9a-f]{16}-01$")
    input: Payload
    environment: Payload
    artifact_requirements: list[str] = Field(default_factory=list, max_length=100)
    target: TargetPublish


class ExecutionResult(Contract):
    status: Literal["succeeded", "failed", "cancelled", "timed_out", "unknown"]
    output: Payload | None = None
    error: str | None = Field(default=None, max_length=2000)
    remote_operation_id: str | None = Field(default=None, max_length=500)
    stopped_confirmed: bool = False
    cleanup_status: Literal["pending", "succeeded", "failed", "unknown"]
    cleanup_error: str | None = Field(default=None, max_length=2000)
    evidence_status: Literal["sealed", "partial", "unavailable"]
    dropped_events: int = Field(ge=0)
    evidence_details: Payload = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_result(self):
        if self.status in {"cancelled", "timed_out"} and not self.stopped_confirmed:
            raise ValueError("cancelled/timed_out requires confirmation the target stopped")
        if self.status == "succeeded" and self.output is None:
            raise ValueError("successful execution requires output")
        if self.status in {"failed", "unknown"} and not self.error:
            raise ValueError("failed/unknown execution requires a reason")
        if self.cleanup_status == "failed" and not self.cleanup_error:
            raise ValueError("cleanup failure requires a reason")
        return self


class ExecutionProgress(Contract):
    state: Literal["preparing", "running"]
    remote_operation_id: str | None = Field(default=None, max_length=500)


class Resolution(Contract):
    status: Literal["succeeded", "failed", "cancelled", "timed_out"]
    reason: str = Field(min_length=1, max_length=2000)
    stopped_confirmed: Literal[True]
    output: Payload | None = None


class TargetAdapter(Protocol):
    def capabilities(self) -> TargetCapabilities: ...
    def prepare(self, request: ExecutionInput) -> None: ...
    def execute(self, request: ExecutionInput) -> ExecutionResult: ...
    def cleanup(self, request: ExecutionInput) -> None: ...
