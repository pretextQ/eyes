from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from eyes.contracts.base import Contract, Payload


class ScoreSemantics(Contract):
    minimum: float
    maximum: float
    direction: Literal["higher", "lower"]
    threshold: float
    aggregation: Literal["mean"] = "mean"

    @model_validator(mode="after")
    def valid_range(self):
        if not self.minimum < self.maximum:
            raise ValueError("minimum must be below maximum")
        if not self.minimum <= self.threshold <= self.maximum:
            raise ValueError("threshold must be within range")
        return self


class ScorerPublish(Contract):
    name: str = Field(min_length=1, max_length=200)
    plugin: str = Field(min_length=1, max_length=120)
    implementation_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    config: Payload = Field(default_factory=dict)
    secret_refs: dict[str, str] = Field(default_factory=dict)
    required_evidence: list[Literal["input", "output", "events", "artifacts", "sealed"]] = Field(
        default_factory=lambda: ["output"]
    )
    numeric: ScoreSemantics | None = None
    timeout_seconds: int = Field(default=60, ge=1, le=86400)


class EvidenceView(Contract):
    manifest_id: UUID
    status: Literal["sealed", "partial", "unavailable", "expired"]
    references: list[str]
    events: list[Payload]
    artifacts: list[Payload]
    dropped_events: int | None


class ScoreInput(Contract):
    score_run_id: UUID
    attempt_id: UUID
    case: Payload
    result: Payload
    evidence: EvidenceView
    scorer: ScorerPublish
    traceparent: str
    execution_trace_id: str
    execution_root_span_id: str | None = None
    deadline: datetime | None = None


class ScoreAssignment(Contract):
    score_run_id: UUID
    attempt_id: UUID
    manifest_id: UUID
    deadline: datetime

    @field_validator("deadline")
    @classmethod
    def aware_deadline(cls, value):
        if value.tzinfo is None:
            raise ValueError("score deadline requires a timezone")
        return value


class ScoreOutput(Contract):
    status: Literal["completed", "error", "insufficient_evidence", "skipped"]
    verdict: Literal["pass", "fail", "not_applicable"] | None = None
    value: float | None = None
    reason: str = Field(min_length=1, max_length=5000)
    evidence_refs: list[str] = Field(default_factory=list, max_length=1000)
    completed_at: datetime | None = None

    @field_validator("completed_at")
    @classmethod
    def aware_completion(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("score completion time requires a timezone")
        return value

    @model_validator(mode="after")
    def separate_status_and_verdict(self):
        if self.status == "completed" and self.verdict is None:
            raise ValueError("completed scoring requires a verdict")
        if self.status != "completed" and (self.verdict is not None or self.value is not None):
            raise ValueError("incomplete scoring must not contain a verdict or numeric value")
        if self.verdict in {"pass", "fail"} and not self.evidence_refs:
            raise ValueError("pass/fail requires evidence references")
        if self.verdict == "not_applicable" and self.value is not None:
            raise ValueError("not_applicable must not have a numeric score")
        return self


class Scorer(Protocol):
    def score(self, request: ScoreInput) -> ScoreOutput: ...
