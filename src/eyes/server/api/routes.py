from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select

from eyes.contracts.dataset import CaseDefinition, DatasetImport
from eyes.contracts.evidence import ArtifactMetadata, EventBatch, ExecutionEvent
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
    ExperimentCreate,
    LeaseRequest,
    RunnerRegister,
    WorkClaim,
)
from eyes.server.api.dependencies import ArtifactReader, Database, Manager, Reader, RunnerIdentity
from eyes.server.catalog import service as catalog
from eyes.server.domain import DomainError, public_record, scoped
from eyes.server.evaluation import service as evaluation
from eyes.server.evidence import service as evidence
from eyes.server.scheduling import service as scheduling
from eyes.server.storage.database import scheduling_lock
from eyes.server.storage.models import (
    Attempt,
    Credential,
    DatasetVersion,
    Event,
    Experiment,
    Manifest,
    ResolutionRecord,
    Runner,
    ScorerVersion,
    TargetVersion,
    WorkItem,
    now,
)

router = APIRouter(prefix="/v1")
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0)]


def record(value):
    return {"schema_version": "1.0", **public_record(value)}


def collection(items):
    return {"schema_version": "1.0", "items": [public_record(item) for item in items]}


@router.post("/targets", status_code=201)
def publish_target(body: TargetPublish, session: Database, user: Manager):
    return record(catalog.publish(session, user.project_id, body))


@router.post("/scorers", status_code=201)
def publish_scorer(body: ScorerPublish, session: Database, user: Manager):
    return record(catalog.publish(session, user.project_id, body))


@router.post("/datasets/import", status_code=201)
def import_dataset(body: DatasetImport, session: Database, user: Manager, request: Request):
    return record(
        catalog.import_dataset(session, user.project_id, body, request.app.state.settings)
    )


@router.get("/catalog/{kind}")
def list_catalog(
    kind: Literal["targets", "datasets", "scorers"],
    session: Database,
    user: Reader,
    limit: Limit = 50,
    offset: Offset = 0,
):
    model = {"targets": TargetVersion, "datasets": DatasetVersion, "scorers": ScorerVersion}[kind]
    return collection(catalog.list_versions(session, user.project_id, model, limit, offset))


@router.get("/catalog/{kind}/{version_id}")
def get_version(
    kind: Literal["targets", "datasets", "scorers"],
    version_id: UUID,
    session: Database,
    user: Reader,
):
    model = {"targets": TargetVersion, "datasets": DatasetVersion, "scorers": ScorerVersion}[kind]
    return record(scoped(session, model, version_id, user.project_id))


@router.post("/experiments", status_code=201)
def create_experiment(
    body: ExperimentCreate,
    session: Database,
    user: Manager,
    request: Request,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
):
    from eyes.server.experiments import service

    return record(service.create(session, user.project_id, key, body, request.app.state.settings))


@router.get("/experiments")
def list_experiments(session: Database, user: Reader, limit: Limit = 50, offset: Offset = 0):
    return collection(
        session.scalars(
            select(Experiment)
            .where(Experiment.project_id == user.project_id)
            .order_by(Experiment.created_at.desc(), Experiment.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/experiments/{experiment_id}")
def get_experiment(experiment_id: UUID, session: Database, user: Reader):
    return record(scoped(session, Experiment, experiment_id, user.project_id))


@router.get("/experiments/{experiment_id}/results")
def get_results(experiment_id: UUID, session: Database, user: Reader):
    from eyes.server.experiments import service

    return service.summary(session, scoped(session, Experiment, experiment_id, user.project_id))


@router.get("/experiments/{experiment_id}/case-runs")
def get_case_runs(
    experiment_id: UUID, session: Database, user: Reader, limit: Limit = 50, offset: Offset = 0
):
    from eyes.server.experiments import service

    experiment = scoped(session, Experiment, experiment_id, user.project_id)
    return {
        "schema_version": "1.0",
        "items": service.run_details(session, experiment, limit, offset),
    }


@router.post("/experiments/{experiment_id}/cancel")
def cancel_experiment(experiment_id: UUID, session: Database, user: Manager):
    return record(scheduling.cancel(session, user.project_id, experiment_id))


@router.post("/runners/register")
def register_runner(body: RunnerRegister, session: Database, runner: RunnerIdentity):
    return scheduling.register(session, runner, body)


@router.post("/work/claim")
def claim_work(body: WorkClaim, session: Database, runner: RunnerIdentity, request: Request):
    return {
        "schema_version": "1.0",
        "work": scheduling.claim(session, runner, body, request.app.state.settings),
    }


@router.post("/work/{work_id}/heartbeat")
def heartbeat(
    work_id: UUID, body: LeaseRequest, session: Database, runner: RunnerIdentity, request: Request
):
    return scheduling.heartbeat(session, runner, work_id, body, request.app.state.settings)


class ProgressSubmission(LeaseRequest):
    progress: ExecutionProgress


class ExecutionSubmission(LeaseRequest):
    result: ExecutionResult


class ScoreSubmission(LeaseRequest):
    result: ScoreOutput


@router.post("/work/{work_id}/score-input")
def score_input(
    work_id: UUID, body: LeaseRequest, session: Database, runner: RunnerIdentity, request: Request
):
    payload = scheduling.score_input(session, runner, work_id, body)
    response = JSONResponse(content=jsonable_encoder(payload))
    if len(response.body) > request.app.state.settings.max_score_input_bytes:
        raise DomainError(413, "score_input_too_large", "score input exceeds configured byte limit")
    return response


@router.post("/work/{work_id}/progress")
def progress(work_id: UUID, body: ProgressSubmission, session: Database, runner: RunnerIdentity):
    return scheduling.progress(session, runner, work_id, body, body.progress)


@router.post("/work/{work_id}/execution-result")
def execution_result(
    work_id: UUID,
    body: ExecutionSubmission,
    session: Database,
    runner: RunnerIdentity,
    request: Request,
):
    return scheduling.finish(
        session,
        runner,
        work_id,
        body,
        body.result,
        request.app.state.artifacts,
        request.app.state.settings,
    )


@router.post("/work/{work_id}/score-result")
def score_result(
    work_id: UUID,
    body: ScoreSubmission,
    session: Database,
    runner: RunnerIdentity,
    request: Request,
):
    return scheduling.finish(
        session,
        runner,
        work_id,
        body,
        body.result,
        request.app.state.artifacts,
        request.app.state.settings,
    )


@router.post("/attempts/{attempt_id}/resolve")
def resolve_attempt(attempt_id: UUID, body: Resolution, session: Database, user: Manager):
    return record(scheduling.resolve(session, user, attempt_id, body))


@router.post("/attempts/{attempt_id}/rescore", status_code=201)
def rescore_attempt(attempt_id: UUID, session: Database, user: Manager):
    scheduling_lock(session)
    attempt = scoped(session, Attempt, attempt_id, user.project_id, lock=True)
    scores = evaluation.rescore(session, attempt)
    from eyes.server.storage.models import CaseRun

    scheduling.refresh_experiment(session, session.get(CaseRun, attempt.case_run_id).experiment_id)
    return collection(scores)


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: UUID, session: Database, user: Reader):
    attempt = scoped(session, Attempt, attempt_id, user.project_id)
    return {
        **record(attempt),
        "resolutions": [
            public_record(r)
            for r in session.scalars(
                select(ResolutionRecord)
                .where(ResolutionRecord.attempt_id == attempt.id)
                .order_by(ResolutionRecord.created_at, ResolutionRecord.id)
            )
        ],
    }


@router.post("/events")
def ingest_events(body: EventBatch, session: Database, runner: RunnerIdentity):
    return evidence.ingest(session, runner, body)


@router.get("/attempts/{attempt_id}/events")
def get_events(
    attempt_id: UUID, session: Database, user: Reader, limit: Limit = 100, offset: Offset = 0
):
    scoped(session, Attempt, attempt_id, user.project_id)
    return collection(
        session.scalars(
            select(Event)
            .where(Event.attempt_id == attempt_id)
            .order_by(Event.created_at, Event.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/attempts/{attempt_id}/manifests")
def get_manifests(
    attempt_id: UUID, session: Database, user: Reader, limit: Limit = 50, offset: Offset = 0
):
    scoped(session, Attempt, attempt_id, user.project_id)
    return collection(
        session.scalars(
            select(Manifest)
            .where(Manifest.attempt_id == attempt_id)
            .order_by(Manifest.version)
            .limit(limit)
            .offset(offset)
        )
    )


@router.post("/attempts/{attempt_id}/artifacts", status_code=201)
def initiate_artifact(
    attempt_id: UUID,
    body: ArtifactMetadata,
    session: Database,
    runner: RunnerIdentity,
    request: Request,
):
    return record(
        evidence.initiate_artifact(
            session, runner, attempt_id, body, request.app.state.settings.max_artifact_bytes
        )
    )


@router.put("/artifacts/{artifact_id}/content")
async def upload_artifact(
    artifact_id: UUID, session: Database, runner: RunnerIdentity, request: Request
):
    from starlette.concurrency import run_in_threadpool

    content = await request.body()
    result = await run_in_threadpool(
        evidence.publish_artifact,
        session,
        runner,
        artifact_id,
        content,
        request.app.state.artifacts,
    )
    return jsonable_encoder(record(result))


@router.get("/artifacts/{artifact_id}/content")
def download_artifact(artifact_id: UUID, session: Database, user: ArtifactReader, request: Request):
    path = evidence.download_path(session, user, artifact_id, request.app.state.artifacts)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/operations")
def operations(session: Database, user: Reader):
    counts = session.execute(
        select(WorkItem.kind, WorkItem.status, func.count())
        .where(WorkItem.project_id == user.project_id)
        .group_by(WorkItem.kind, WorkItem.status)
    ).all()
    runners = session.scalars(
        select(Runner).join(Credential).where(Credential.project_id == user.project_id)
    ).all()
    return {
        "schema_version": "1.0",
        "observed_at": now(),
        "work_counts": [
            {"kind": kind, "status": status, "count": count} for kind, status, count in counts
        ],
        "runners": [public_record(r) for r in runners],
    }


@router.get("/contracts")
def contract_schemas(user: Reader):
    models = [
        TargetPublish,
        ExecutionInput,
        ExecutionResult,
        CaseDefinition,
        ScorerPublish,
        ScoreInput,
        ScoreAssignment,
        ScoreOutput,
        ExecutionEvent,
        ArtifactMetadata,
        ClaimedWork,
    ]
    return {
        "schema_version": "1.0",
        "schemas": {model.__name__: model.model_json_schema() for model in models},
    }
