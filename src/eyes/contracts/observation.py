"""Append-only telemetry from an Agent that owns its own execution."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from eyes.contracts.base import Contract, Payload


class ObservationSourceCreate(Contract):
    name: str = Field(min_length=1, max_length=200)


class ObservationEvent(Contract):
    event_id: UUID
    sequence: int = Field(ge=1, le=100000)
    occurred_at: datetime
    type: Literal[
        "run_start",
        "run_end",
        "turn_start",
        "turn_end",
        "input",
        "message_end",
        "tool_start",
        "tool_end",
        "model_start",
        "model_end",
        "model_input",
        "compaction_start",
        "compaction_end",
    ]
    turn: int | None = Field(default=None, ge=1)
    tool_call_id: str | None = Field(default=None, max_length=500)
    trace_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    span_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    parent_span_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    data: Payload = Field(default_factory=dict)
    truncated: bool = False

    @field_validator("occurred_at")
    @classmethod
    def timezone_required(cls, value):
        if value.tzinfo is None:
            raise ValueError("occurred_at must include a timezone")
        return value

    @model_validator(mode="after")
    def lifecycle(self):
        if self.type == "run_start" and self.sequence != 1:
            raise ValueError("run_start must have sequence 1")
        if self.type == "run_end":
            if self.data.get("status") not in {"completed", "failed", "limited", "cancelled"}:
                raise ValueError("run_end requires the Agent's terminal status")
            dropped = self.data.get("dropped_events")
            if type(dropped) is not int or dropped < 0:
                raise ValueError("run_end requires a nonnegative dropped_events count")
        return self


class ObservationBatch(Contract):
    run_id: str = Field(min_length=1, max_length=200)
    session_id: str = Field(min_length=1, max_length=200)
    agent: str = Field(min_length=1, max_length=200)
    model: str = Field(min_length=1, max_length=200)
    capture_body: bool = False
    events: list[ObservationEvent] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_events(self):
        if len({e.sequence for e in self.events}) != len(self.events):
            raise ValueError("duplicate sequence in batch")
        if len({e.event_id for e in self.events}) != len(self.events):
            raise ValueError("duplicate event_id in batch")
        return self
