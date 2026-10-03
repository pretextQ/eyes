from uuid import UUID

from pydantic import Field, model_validator

from eyes.contracts.base import Contract


class GatePolicy(Contract):
    max_regressions: int = Field(default=0, ge=0)
    min_comparable_coverage: float = Field(default=1, ge=0, le=1)
    min_candidate_pass_rate: float = Field(default=1, ge=0, le=1)
    min_execution_success_rate: float = Field(default=1, ge=0, le=1)
    numeric_tolerance: float = Field(default=0, ge=0)


class ScorerPair(Contract):
    baseline_id: UUID
    candidate_id: UUID


class ComparisonCreate(Contract):
    baseline_id: UUID
    candidate_id: UUID
    scorer_pairs: list[ScorerPair] = Field(min_length=1, max_length=20)
    baseline_score_ids: list[UUID] = Field(default_factory=list, max_length=100000)
    candidate_score_ids: list[UUID] = Field(default_factory=list, max_length=100000)
    gate: GatePolicy = Field(default_factory=GatePolicy)

    @model_validator(mode="after")
    def distinct(self):
        if self.baseline_id == self.candidate_id:
            raise ValueError("choose two distinct experiments")
        for field in ("baseline_id", "candidate_id"):
            ids = [getattr(pair, field) for pair in self.scorer_pairs]
            if len(ids) != len(set(ids)):
                raise ValueError("each scorer may appear in one pair only")
        for ids in (self.baseline_score_ids, self.candidate_score_ids):
            if len(ids) != len(set(ids)):
                raise ValueError("score overrides must be unique")
        return self
