from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from eyes.contracts.base import Contract, Payload


class ExecutionEvent(Contract):
    event_id: UUID
    producer_id: str = Field(min_length=1, max_length=200)
    attempt_id: UUID
    trace_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    span_id: str = Field(pattern=r"^[0-9a-f]{16}$")
    parent_span_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    sequence: int = Field(ge=0)
    occurred_at: datetime
    type: str = Field(min_length=1, max_length=100)
    source: Literal["runner", "sdk", "target_trace"]
    linked_trace_ids: list[str] = Field(default_factory=list, max_length=20)
    data: Payload = Field(default_factory=dict)

    @field_validator("linked_trace_ids")
    @classmethod
    def valid_trace_links(cls, value):
        import re

        if any(not re.fullmatch(r"[0-9a-f]{32}", item) or int(item, 16) == 0 for item in value):
            raise ValueError("linked trace identifiers must be nonzero 32-character hex strings")
        return value

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("occurred_at requires a timezone")
        return value

    @field_validator("trace_id", "span_id", "parent_span_id")
    @classmethod
    def nonzero_identifier(cls, value):
        if value is not None and int(value, 16) == 0:
            raise ValueError("trace/span identifiers must be nonzero")
        return value


class EventBatch(Contract):
    events: list[ExecutionEvent] = Field(min_length=1, max_length=500)


class ArtifactMetadata(Contract):
    name: str = Field(min_length=1, max_length=200)
    media_type: str = Field(default="application/octet-stream", max_length=120)
    size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class EvidenceClose(Contract):
    status: Literal["sealed", "partial", "unavailable"]
    dropped_events: int = Field(ge=0)
    details: Payload = Field(default_factory=dict)
