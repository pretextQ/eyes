"""Manager attestations about an original operation; never a new execution."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from eyes.contracts.base import Contract, Payload


class ReconciliationEvidence(Contract):
    evidence_id: UUID
    expected_attempt_id: UUID
    expected_task_id: UUID
    expected_run_id: str = Field(min_length=1, max_length=500)
    idempotency_key_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source: Literal["supplier_record", "operator_review"]
    source_reference: UUID
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    observed_at: AwareDatetime
    stopped_confirmed: bool = False
    status: Literal["succeeded", "failed", "cancelled", "timed_out"] | None = None
    billing: Literal["unconfirmed", "not_charged", "charged", "refunded"] = "unconfirmed"
    reason: str = Field(min_length=1, max_length=1000)
    output: Payload | None = None
    apply: bool = False

    @model_validator(mode="after")
    def application_requires_outcome_and_stop(self):
        if self.apply and (not self.stopped_confirmed or self.status is None):
            raise ValueError("application requires both a known outcome and confirmed stop")
        if self.status == "succeeded" and self.output is None:
            raise ValueError("successful outcome requires output")
        return self
