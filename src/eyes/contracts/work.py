from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from eyes.contracts.base import Contract, Payload
from eyes.contracts.target import TargetCapabilities, http_origin


class ExperimentCreate(Contract):
    target_version_id: UUID
    dataset_version_id: UUID
    scorer_version_ids: list[UUID] = Field(min_length=1, max_length=20)
    concurrency: int = Field(default=1, ge=1, le=1000)
    timeout_seconds: int = Field(default=300, ge=1, le=86400)
    repetitions: int = Field(default=1, ge=1, le=100)
    attempt_selection: Literal["first_success"] = "first_success"
    parent_experiment_id: UUID | None = None


class RunnerRegister(Contract):
    name: str = Field(min_length=1, max_length=200)
    supported_schema_versions: list[str] = Field(min_length=1)
    adapters: list[str] = Field(default_factory=list, max_length=100)
    scorers: list[str] = Field(default_factory=list, max_length=100)
    python_agents: dict[str, TargetCapabilities] = Field(default_factory=dict, max_length=1000)
    http_origins: list[str] = Field(default_factory=list, max_length=1000)

    @field_validator("http_origins")
    @classmethod
    def normalize_origins(cls, value):
        return sorted({http_origin(item) for item in value})


class WorkClaim(Contract):
    runner_id: UUID
    kind: Literal["execute", "score"]


class LeaseRequest(Contract):
    runner_id: UUID
    lease_token: UUID


class ClaimedWork(Contract):
    work_item_id: UUID
    kind: Literal["execute", "score"]
    lease_token: UUID
    lease_expires_at: datetime
    lease_seconds: int = Field(ge=1)
    payload: Payload

    @field_validator("lease_expires_at")
    @classmethod
    def aware_expiry(cls, value):
        if value.tzinfo is None:
            raise ValueError("lease expiry requires a timezone")
        return value
