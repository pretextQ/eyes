"""External Agent protocol v1 contracts, independent of Runner and storage.

Export the language-neutral type schemas with:
    python -m eyes.contracts.agent_protocol

The wire semantics and HTTP binding are specified in docs/agent-protocol.md.
These types do not enable a runtime adapter or an Agent server by themselves.
"""

import json
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator
from pydantic.json_schema import models_json_schema

from eyes.contracts.base import Payload

TERMINAL_STATES = {"succeeded", "failed", "cancelled", "timed_out"}
type RunState = Literal[
    "accepted",
    "queued",
    "running",
    "cancel_requested",
    "succeeded",
    "failed",
    "cancelled",
    "timed_out",
    "unknown",
]


class Value(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Message(Value):
    # Required on the wire; never silently interpret an unversioned message as v1.
    protocol_version: Literal["1.0"]


class AgentCapabilities(Message):
    agent_id: str = Field(min_length=1, max_length=200)
    agent_version: str | None
    input_schema: Payload
    max_concurrency: int = Field(ge=1, le=1000)
    session_isolation: bool
    environment_isolation: bool
    cancellation: bool
    resources: bool
    events: bool
    artifacts: bool
    # Running and unknown operations must never expire their deduplication records.
    terminal_retention_seconds: int = Field(ge=86400)

    @model_validator(mode="after")
    def concurrency_requires_isolation(self):
        if self.max_concurrency > 1 and not (self.session_isolation and self.environment_isolation):
            raise ValueError("parallel tasks require session and environment isolation")
        return self


class AgentResource(Value):
    name: str = Field(min_length=1, max_length=200)
    # Input uploads are scoped to the authenticated caller, never host filesystem paths.
    resource_id: UUID
    media_type: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AgentTask(Message):
    task_id: UUID
    attempt_id: UUID
    idempotency_key: str = Field(pattern=r"^[A-Za-z0-9._:-]{1,200}$")
    deadline: AwareDatetime
    input: Payload
    resources: list[AgentResource] = Field(default_factory=list, max_length=100)
    traceparent: str = Field(pattern=r"^00-[0-9a-f]{32}-[0-9a-f]{16}-0[01]$")

    @model_validator(mode="after")
    def unique_resources_and_valid_trace(self):
        names = [resource.name for resource in self.resources]
        if len(set(names)) != len(names):
            raise ValueError("resource names must be unique within a task")
        _, trace_id, span_id, _ = self.traceparent.split("-")
        if int(trace_id, 16) == 0 or int(span_id, 16) == 0:
            raise ValueError("trace and span identifiers must be nonzero")
        return self


class AgentProblem(Value):
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    message: str = Field(min_length=1, max_length=2000)


class AgentEvidence(Value):
    status: Literal["collecting", "sealed", "partial", "unavailable"]
    dropped_events: int | None = Field(ge=0)
    details: Payload = Field(default_factory=dict)

    @model_validator(mode="after")
    def sealed_requires_known_capture(self):
        if self.status == "sealed" and self.dropped_events != 0:
            raise ValueError("sealed evidence requires zero known dropped events")
        return self


class AgentArtifact(Value):
    artifact_id: UUID
    name: str = Field(min_length=1, max_length=200)
    media_type: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class AgentResult(Message):
    run_id: UUID
    status: Literal["succeeded", "failed", "cancelled", "timed_out", "unknown"]
    output: Payload | None
    error: AgentProblem | None
    stopped_confirmed: bool
    completed_at: AwareDatetime | None
    cleanup_status: Literal["succeeded", "failed", "unknown"]
    evidence: AgentEvidence
    artifacts: list[AgentArtifact] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def outcome_is_consistent(self):
        if self.status in TERMINAL_STATES and (
            not self.stopped_confirmed or self.completed_at is None
        ):
            raise ValueError("a terminal result requires confirmed stop and completion time")
        if self.status == "unknown" and self.completed_at is not None:
            raise ValueError("unknown has no confirmed outcome completion time")
        if self.status == "succeeded" and (self.output is None or self.error is not None):
            raise ValueError("success requires output and no execution error")
        if self.status in {"failed", "unknown"} and self.error is None:
            raise ValueError("failed and unknown require an explanation")
        ids = [artifact.artifact_id for artifact in self.artifacts]
        names = [artifact.name for artifact in self.artifacts]
        if len(set(ids)) != len(ids) or len(set(names)) != len(names):
            raise ValueError("artifact identifiers and names must be unique within a result")
        return self


class AgentRun(Message):
    run_id: UUID
    task_id: UUID
    attempt_id: UUID
    status: RunState
    revision: int = Field(ge=1)
    observed_at: AwareDatetime
    result: AgentResult | None

    @model_validator(mode="after")
    def snapshot_is_consistent(self):
        outcome = self.status in TERMINAL_STATES or self.status == "unknown"
        if outcome != (self.result is not None):
            raise ValueError("only terminal and unknown snapshots must carry a result")
        if self.result and (self.result.run_id != self.run_id or self.result.status != self.status):
            raise ValueError("result must belong to the same run and state")
        return self


class AgentCancelResult(Message):
    run: AgentRun
    accepted: bool
    stopped_confirmed: bool

    @model_validator(mode="after")
    def cancellation_is_consistent(self):
        confirmed = bool(self.run.result and self.run.result.stopped_confirmed)
        if self.stopped_confirmed != confirmed:
            raise ValueError("stop confirmation must match the run result")
        if self.accepted and self.run.status not in (
            TERMINAL_STATES | {"cancel_requested", "unknown"}
        ):
            raise ValueError("accepted cancellation must be reflected in the run state")
        return self


class AgentEvent(Value):
    event_id: UUID
    run_id: UUID
    sequence: int = Field(ge=0)
    occurred_at: AwareDatetime
    type: str = Field(min_length=1, max_length=120)
    data: Payload


class AgentEventPage(Message):
    run_id: UUID
    items: list[AgentEvent] = Field(max_length=200)
    next_cursor: str | None = Field(max_length=512)
    evidence: AgentEvidence

    @model_validator(mode="after")
    def events_belong_to_run(self):
        if any(event.run_id != self.run_id for event in self.items):
            raise ValueError("events must belong to the requested run")
        sequences = [event.sequence for event in self.items]
        ids = [event.event_id for event in self.items]
        if sequences != sorted(set(sequences)) or len(set(ids)) != len(ids):
            raise ValueError("events must be unique and ordered by sequence")
        return self


class AgentError(Message):
    error: AgentProblem


def main():
    """Generate schemas for other languages; HTTP semantics remain in the specification."""
    _, schemas = models_json_schema(
        [
            (model, "validation")
            for model in (
                AgentCapabilities,
                AgentResource,
                AgentTask,
                AgentRun,
                AgentResult,
                AgentCancelResult,
                AgentEventPage,
                AgentArtifact,
                AgentError,
            )
        ],
        title="Eyes external Agent protocol 1.0",
    )
    print(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "urn:eyes:agent-protocol:1.0",
                **schemas,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
