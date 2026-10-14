from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func, select
from starlette.background import BackgroundTask

from eyes.contracts.cancellation import CancellationRequest
from eyes.contracts.comparison import ComparisonCreate
from eyes.contracts.dataset import DatasetImport
from eyes.contracts.evidence import ArtifactMetadata, EventBatch, EvidenceClose
from eyes.contracts.schema import public_models
from eyes.contracts.scorer import ScorerPublish
from eyes.contracts.target import (
    Resolution,
    TargetPublish,
)
from eyes.contracts.work import (
    ExecutionSubmission,
    ExperimentBatchCreate,
    ExperimentCreate,
    LeaseRequest,
    ProgressSubmission,
    ReconciliationClaim,
    ReconciliationSubmission,
    RecoveryEventSubmission,
    RunnerRegister,
    ScoreSubmission,
    WorkClaim,
)
from eyes.server.api.dependencies import ArtifactReader, Database, Manager, Reader, RunnerIdentity
from eyes.server.catalog import service as catalog
from eyes.server.domain import DomainError, public_record, scoped
from eyes.server.evaluation import service as evaluation
from eyes.server.evidence import service as evidence
from eyes.server.experiments import batches, cancellation
from eyes.server.operations import capacity
from eyes.server.scheduling import reconciliation, recovery
from eyes.server.scheduling import service as scheduling
from eyes.server.storage.database import scheduling_lock
from eyes.server.storage.models import (
    Attempt,
    CaseRun,
    ComparisonReport,
    Credential,
    DatasetVersion,
    Event,
    EvidenceWait,
    Experiment,
    ExperimentBatch,
    Manifest,
    ResolutionRecord,
    Runner,
    ScoreRun,
    ScorerVersion,
    TargetVersion,
    WorkItem,
    now,
)

router = APIRouter(prefix="/v1")


@router.get("/operations/capacity", tags=["operations"])
def capacity_status(request: Request, session: Database, user: Manager):
    return capacity.status(session, request.app.state.settings, user.project_id)


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


@router.post("/experiment-batches", status_code=201)
def create_batch(
    body: ExperimentBatchCreate,
    session: Database,
    user: Manager,
    request: Request,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
):
    batch = batches.create(session, user.project_id, key, body, request.app.state.settings)
    return batches.detail(session, batch)


@router.get("/experiment-batches")
def list_batches(session: Database, user: Reader, limit: Limit = 50, offset: Offset = 0):
    return {
        "schema_version": "1.0",
        "items": batches.list_batches(session, user.project_id, limit, offset),
    }


@router.get("/experiment-batches/{batch_id}")
def get_batch(batch_id: UUID, session: Database, user: Reader):
    return batches.detail(session, scoped(session, ExperimentBatch, batch_id, user.project_id))


@router.post("/experiment-batches/{batch_id}/cancel")
def cancel_batch(
    batch_id: UUID,
    session: Database,
    user: Manager,
    body: CancellationRequest | None = None,
    key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
):
    audit, duplicate = cancellation.request(
        session, user, "batch", batch_id, body.reason if body else None, key
    )
    return cancellation_response(session, user, audit, duplicate)


def cancellation_response(session, user, audit, duplicate):
    metadata = {"cancellation_audit": cancellation.view(audit), "duplicate": duplicate}
    if audit.http_status != 200:
        # Returning a response commits the failed handling fact; raising rolls it back.
        return JSONResponse(
            status_code=audit.http_status,
            content=jsonable_encoder(
                {
                    "schema_version": "1.0",
                    "error": {
                        "code": audit.result["error_code"],
                        "message": "cancellation object not available in this project",
                    },
                    **metadata,
                }
            ),
        )
    model = Experiment if audit.object_kind == "experiment" else ExperimentBatch
    obj = session.scalar(
        select(model).where(model.id == audit.object_id, model.project_id == user.project_id)
    )
    # Replay after deletion can still return the immutable original handling result.
    payload = (
        (record(obj) if model is Experiment else batches.detail(session, obj))
        if obj
        else {
            "schema_version": "1.0",
            "id": audit.object_id,
            "object_deleted": True,
        }
    )
    return {**payload, **metadata}


@router.get("/cancellation-audits")
def cancellation_history(
    session: Database,
    user: Reader,
    limit: Limit = 50,
    offset: Offset = 0,
    object_kind: Literal["experiment", "batch"] | None = None,
    object_id: UUID | None = None,
    parent_id: UUID | None = None,
):
    return {
        "schema_version": "1.0",
        "items": cancellation.listing(
            session, user.project_id, limit, offset, object_kind, object_id, parent_id
        ),
    }


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


@router.get("/experiments/{experiment_id}/case-runs/{case_run_id}")
def get_case_run(experiment_id: UUID, case_run_id: UUID, session: Database, user: Reader):
    from eyes.server.experiments import service

    experiment = scoped(session, Experiment, experiment_id, user.project_id)
    run = session.scalar(
        select(CaseRun).where(CaseRun.id == case_run_id, CaseRun.experiment_id == experiment.id)
    )
    if run is None:
        raise DomainError(404, "not_found", "case run does not belong to this experiment")
    return {"schema_version": "1.0", **service.run_detail(session, run)}


@router.post("/experiments/{experiment_id}/cancel")
def cancel_experiment(
    experiment_id: UUID,
    session: Database,
    user: Manager,
    body: CancellationRequest | None = None,
    key: Annotated[
        str | None, Header(alias="Idempotency-Key", min_length=1, max_length=200)
    ] = None,
):
    audit, duplicate = cancellation.request(
        session, user, "experiment", experiment_id, body.reason if body else None, key
    )
    return cancellation_response(session, user, audit, duplicate)


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


@router.post("/reconciliation/claim")
def claim_reconciliation(body: ReconciliationClaim, session: Database, runner: RunnerIdentity):
    handler = recovery.claim if body.evidence_recovery else reconciliation.claim
    return {"schema_version": "1.0", "query": handler(session, runner, body)}


@router.post("/work/{work_id}/recovery-observation")
def recovery_observation(
    work_id: UUID, body: ReconciliationSubmission, session: Database, runner: RunnerIdentity
):
    return recovery.observe(session, runner, work_id, body)


@router.post("/work/{work_id}/recovery-events")
def recovery_events(
    work_id: UUID, body: RecoveryEventSubmission, session: Database, runner: RunnerIdentity
):
    return recovery.events(session, runner, work_id, body)


@router.put("/work/{work_id}/recovery-artifacts/{artifact_id}")
async def recovery_artifact(
    work_id: UUID,
    artifact_id: UUID,
    lease_token: UUID,
    session: Database,
    runner: RunnerIdentity,
    request: Request,
):
    from starlette.concurrency import run_in_threadpool

    content = await request.body()
    if len(content) > request.app.state.settings.max_artifact_bytes:
        raise DomainError(413, "artifact_too_large", "artifact exceeds configured size limit")
    return await run_in_threadpool(
        recovery.artifact,
        session,
        runner,
        work_id,
        lease_token,
        artifact_id,
        content,
        request.app.state.artifacts,
        request.app.state.settings.max_artifact_bytes,
    )


@router.post("/work/{work_id}/recovery-close")
def recovery_close(work_id: UUID, body: LeaseRequest, session: Database, runner: RunnerIdentity):
    return recovery.close(session, runner, work_id, body)


@router.post("/work/{work_id}/reconciliation-result")
def reconciliation_result(
    work_id: UUID,
    body: ReconciliationSubmission,
    session: Database,
    runner: RunnerIdentity,
):
    return reconciliation.submit(session, runner, work_id, body)


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

    scheduling.refresh_experiment(session, session.get(CaseRun, attempt.case_run_id).experiment_id)
    return collection(scores)


@router.get("/attempts/{attempt_id}")
def get_attempt(attempt_id: UUID, session: Database, user: Reader):
    attempt = scoped(session, Attempt, attempt_id, user.project_id)
    return {
        **record(attempt),
        "evidence_waits": [
            public_record(w)
            for w in session.scalars(
                select(EvidenceWait)
                .where(EvidenceWait.attempt_id == attempt.id)
                .order_by(EvidenceWait.created_at, EvidenceWait.id)
            )
        ],
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
    # Open while the transaction's maintenance lock still protects the path.
    # POSIX keeps this descriptor valid if retention unlinks after authorization.
    stream = path.open("rb")

    def chunks():
        try:
            while chunk := stream.read(64 * 1024):
                yield chunk
        finally:
            stream.close()

    return StreamingResponse(
        chunks(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": "attachment", "X-Content-Type-Options": "nosniff"},
        background=BackgroundTask(stream.close),
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
    dropped = Attempt.result["dropped_events"].as_integer()
    drop_summary = session.execute(
        select(func.sum(dropped), func.count(Attempt.id).filter(dropped.is_(None))).where(
            Attempt.project_id == user.project_id
        )
    ).one()
    return {
        "schema_version": "1.0",
        "observed_at": now(),
        "work_counts": [
            {"kind": kind, "status": status, "count": count} for kind, status, count in counts
        ],
        "runners": [public_record(r) for r in runners],
        "event_drops": {"reported_total": drop_summary[0], "unknown_attempts": drop_summary[1]},
        "waiting_evidence": session.scalar(
            select(func.count())
            .select_from(EvidenceWait)
            .join(Attempt)
            .where(Attempt.project_id == user.project_id, EvidenceWait.status == "waiting")
        ),
        "oldest_queued_at": session.scalar(
            select(func.min(WorkItem.created_at)).where(
                WorkItem.project_id == user.project_id, WorkItem.status == "queued"
            )
        ),
        "score_errors": session.scalar(
            select(func.count())
            .select_from(ScoreRun)
            .join(Attempt)
            .where(Attempt.project_id == user.project_id, ScoreRun.status == "error")
        ),
    }


@router.get("/contracts")
def contract_schemas(user: Reader):
    models = public_models()
    return {
        "schema_version": "1.0",
        "schemas": {model.__name__: model.model_json_schema() for model in models},
    }


@router.post("/comparisons", status_code=201)
def create_comparison(
    body: ComparisonCreate,
    session: Database,
    user: Manager,
    key: Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=200)],
):
    from eyes.server.comparison import service

    return record(service.create(session, user.project_id, key, body))


@router.get("/comparisons")
def list_comparisons(session: Database, user: Reader, limit: Limit = 50, offset: Offset = 0):
    return collection(
        session.scalars(
            select(ComparisonReport)
            .where(ComparisonReport.project_id == user.project_id)
            .order_by(ComparisonReport.created_at.desc(), ComparisonReport.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.get("/comparisons/{report_id}")
def get_comparison(report_id: UUID, session: Database, user: Reader):
    return record(scoped(session, ComparisonReport, report_id, user.project_id))


@router.get("/comparisons/{report_id}/gate")
def comparison_gate(report_id: UUID, session: Database, user: Reader):
    report = scoped(session, ComparisonReport, report_id, user.project_id)
    return {
        "schema_version": "1.0",
        "report_id": report.id,
        "report_digest": report.digest,
        **report.content["gate"],
    }


@router.post("/attempts/{attempt_id}/evidence-close")
def close_evidence(
    attempt_id: UUID, body: EvidenceClose, session: Database, runner: RunnerIdentity
):
    scheduling_lock(session)
    manifest = evidence.close(session, runner, attempt_id, body)
    from eyes.server.storage.models import CaseRun

    attempt = session.get(Attempt, attempt_id)
    run = session.get(CaseRun, attempt.case_run_id)
    for experiment_id in evaluation.advance_waits(session, experiment_id=run.experiment_id):
        scheduling.refresh_experiment(session, experiment_id)
    return record(manifest)


@router.post("/score-runs/{score_id}/retry", status_code=201)
def retry_score(score_id: UUID, session: Database, user: Manager):
    from eyes.server.storage.models import CaseRun

    scheduling_lock(session)
    score = evaluation.retry(session, user.project_id, score_id)
    attempt = session.get(Attempt, score.attempt_id)
    scheduling.refresh_experiment(session, session.get(CaseRun, attempt.case_run_id).experiment_id)
    return record(score)
