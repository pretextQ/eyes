"""Export ordinary control contracts; external Agent protocol has its own exporter."""

import json

from pydantic.json_schema import models_json_schema

from eyes.contracts.comparison import ComparisonCreate
from eyes.contracts.dataset import CaseDefinition, DatasetImport
from eyes.contracts.evidence import ArtifactMetadata, EventBatch, EvidenceClose, ExecutionEvent
from eyes.contracts.observation import ObservationBatch, ObservationSourceCreate
from eyes.contracts.scorer import ScoreAssignment, ScoreInput, ScoreOutput, ScorerPublish
from eyes.contracts.target import (
    ExecutionInput,
    ExecutionProgress,
    ExecutionResult,
    Resolution,
    TargetPublish,
)
from eyes.contracts.work import (
    ClaimedWork,
    ExecutionSubmission,
    ExperimentBatchCreate,
    ExperimentCreate,
    LeaseRequest,
    ProgressSubmission,
    ReconciliationAssignment,
    ReconciliationClaim,
    ReconciliationSubmission,
    RecoveryEventSubmission,
    RunnerRegister,
    ScoreSubmission,
    WorkClaim,
)


def public_models():
    return (
        ComparisonCreate,
        CaseDefinition,
        DatasetImport,
        ArtifactMetadata,
        EventBatch,
        EvidenceClose,
        ExecutionEvent,
        ObservationBatch,
        ObservationSourceCreate,
        ScoreAssignment,
        ScoreInput,
        ScoreOutput,
        ScorerPublish,
        ExecutionInput,
        ExecutionProgress,
        ExecutionResult,
        Resolution,
        TargetPublish,
        ClaimedWork,
        ExecutionSubmission,
        ExperimentBatchCreate,
        ExperimentCreate,
        LeaseRequest,
        ProgressSubmission,
        ReconciliationAssignment,
        ReconciliationClaim,
        ReconciliationSubmission,
        RecoveryEventSubmission,
        RunnerRegister,
        ScoreSubmission,
        WorkClaim,
    )


def main():
    _, schemas = models_json_schema(
        [(model, "validation") for model in public_models()], title="Eyes control contracts 1.0"
    )
    print(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "$id": "urn:eyes:control-contracts:1.0",
                **schemas,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
