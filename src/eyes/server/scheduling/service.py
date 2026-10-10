import secrets
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from eyes.contracts.scorer import ScoreAssignment, ScoreOutput
from eyes.contracts.target import ExecutionProgress, ExecutionResult, Resolution, http_origin
from eyes.contracts.work import LeaseRequest, RunnerRegister, WorkClaim
from eyes.server.config import Settings
from eyes.server.domain import DomainError, digest, scoped
from eyes.server.evaluation import service as evaluation
from eyes.server.evidence import service as evidence
from eyes.server.storage.database import scheduling_lock
from eyes.server.storage.models import (
    Attempt,
    CaseRun,
    CaseVersion,
    Credential,
    EvidenceWait,
    Experiment,
    Project,
    ResolutionRecord,
    Runner,
    ScoreRun,
    ScorerVersion,
    Target,
    TargetVersion,
    WorkItem,
    now,
)


def register(session: Session, credential: Credential, request: RunnerRegister):
    if "1.0" not in request.supported_schema_versions:
        raise DomainError(422, "protocol_version", "Runner must support schema version 1.0")
    # Updating plugin capabilities while a lease is held could invalidate execution.
    scheduling_lock(session)
    runner = session.scalar(select(Runner).where(Runner.credential_id == credential.id))
    if runner is None:
        runner = Runner(
            credential_id=credential.id,
            name=request.name,
            capabilities=request.model_dump(mode="json"),
        )
        session.add(runner)
    else:
        active = session.scalar(
            select(func.count())
            .select_from(WorkItem)
            .where(WorkItem.runner_id == runner.id, WorkItem.reserved.is_(True))
        )
        if active and runner.capabilities != request.model_dump(mode="json"):
            raise DomainError(
                409, "runner_busy", "cannot change capabilities while holding capacity"
            )
        runner.name = request.name
        runner.capabilities = request.model_dump(mode="json")
        runner.last_seen_at = now()
    session.flush()
    return {"schema_version": "1.0", "runner_id": runner.id, "negotiated_schema_version": "1.0"}


def authorized_runner(session: Session, credential: Credential, runner_id: UUID):
    runner = session.scalar(
        select(Runner).where(Runner.id == runner_id, Runner.credential_id == credential.id)
    )
    if runner is None:
        raise DomainError(403, "runner_identity", "Runner registration does not match credential")
    return runner


def authorize_work(credential: Credential, work: WorkItem):
    if work.kind not in credential.work_kinds or (
        credential.target_ids and str(work.target_id) not in credential.target_ids
    ):
        raise DomainError(403, "work_scope", "credential does not authorize this work")


def reservations(session: Session, kind: str, **filters):
    query = (
        select(func.count())
        .select_from(WorkItem)
        .where(WorkItem.kind == kind, WorkItem.reserved.is_(True))
    )
    for key, value in filters.items():
        query = query.where(getattr(WorkItem, key) == value)
    return session.scalar(query)


def supports_target(capabilities: dict, target: dict) -> bool:
    requested = target["capabilities"]
    adapter = requested["adapter"]
    if adapter == "python":
        available = capabilities.get("python_agents", {}).get(target["config"].get("agent"))
        if available is None:
            return False
        return all(
            not requested[key] or available[key]
            for key in (
                "session_isolation",
                "environment_isolation",
                "cancellation",
                "idempotency",
                "reconciliation",
            )
        ) and not (set(requested["observation"]) - set(available["observation"]))
    if adapter == "agent_http":
        from eyes.adapters.agent_http import AgentHttpConfig, target_capabilities

        try:
            config = AgentHttpConfig.model_validate(target["config"])
            return (
                http_origin(config.url) in capabilities.get("http_origins", [])
                and requested == target_capabilities(config.discovery).model_dump(mode="json")
                and target["concurrency_limit"] <= config.discovery.max_concurrency
            )
        except TypeError, ValueError, AttributeError:
            return False
    if adapter == "http":
        config = target["config"]
        if not config.get("url"):
            return False
        if requested["cancellation"] and not config.get("cancel_url"):
            return False
        if requested["reconciliation"] and not config.get("reconcile_url"):
            return False
        if set(requested["observation"]) != {"task"}:
            return False
        try:
            return all(
                http_origin(url) in capabilities.get("http_origins", [])
                for url in (
                    config.get("url"),
                    config.get("cancel_url"),
                    config.get("reconcile_url"),
                )
                if url
            )
        except TypeError, ValueError, AttributeError:
            return False
    return adapter in capabilities["adapters"]


def claim(session: Session, credential: Credential, request: WorkClaim, settings: Settings):
    scheduling_lock(session)
    runner = authorized_runner(session, credential, request.runner_id)
    if request.kind not in credential.work_kinds:
        raise DomainError(403, "work_kind", "credential does not authorize this work kind")
    runner.last_seen_at = now()
    project = session.get(Project, credential.project_id)
    global_limit = (
        settings.global_execution_limit
        if request.kind == "execute"
        else settings.global_score_limit
    )
    project_limit = project.execution_limit if request.kind == "execute" else project.score_limit
    if (
        reservations(session, request.kind) >= global_limit
        or reservations(session, request.kind, project_id=project.id) >= project_limit
    ):
        return None
    plugins = runner.capabilities["adapters" if request.kind == "execute" else "scorers"]
    query = select(WorkItem).where(
        WorkItem.project_id == project.id,
        WorkItem.kind == request.kind,
        WorkItem.status == "queued",
        WorkItem.plugin.in_(plugins),
    )
    if credential.target_ids:
        query = query.where(WorkItem.target_id.in_([UUID(tid) for tid in credential.target_ids]))
    if request.kind == "execute":
        from sqlalchemy.orm import aliased

        reserved = aliased(WorkItem)
        target_count = (
            select(func.count())
            .select_from(reserved)
            .where(
                reserved.kind == "execute",
                reserved.reserved.is_(True),
                reserved.target_scope_id == WorkItem.target_scope_id,
            )
            .correlate(WorkItem)
            .scalar_subquery()
        )
        experiment_count = (
            select(func.count())
            .select_from(reserved)
            .where(
                reserved.kind == "execute",
                reserved.reserved.is_(True),
                reserved.experiment_id == WorkItem.experiment_id,
            )
            .correlate(WorkItem)
            .scalar_subquery()
        )
        query = (
            query.join(TargetVersion, TargetVersion.id == WorkItem.target_id)
            .join(Target, Target.id == WorkItem.target_scope_id)
            .join(Experiment, Experiment.id == WorkItem.experiment_id)
            .where(
                target_count < Target.concurrency_limit,
                experiment_count < Experiment.snapshot["request"]["concurrency"].as_integer(),
                or_(
                    WorkItem.plugin != "python",
                    TargetVersion.content["config"]["agent"]
                    .as_string()
                    .in_(list(runner.capabilities.get("python_agents", {}))),
                ),
            )
        )
        if not runner.capabilities.get("http_origins"):
            query = query.where(WorkItem.plugin.not_in(["http", "agent_http"]))
    with session.scalars(
        query.order_by(WorkItem.created_at, WorkItem.id)
        .with_for_update(skip_locked=True, of=WorkItem)
        .execution_options(yield_per=100)
    ) as candidates:
        for work in candidates:
            experiment = session.get(Experiment, work.experiment_id)
            target = session.get(TargetVersion, work.target_id)
            if request.kind == "execute":
                if not supports_target(runner.capabilities, target.content):
                    continue
                if (
                    reservations(session, "execute", target_scope_id=target.target_id)
                    >= target.content["concurrency_limit"]
                ):
                    continue
                if (
                    reservations(session, "execute", experiment_id=experiment.id)
                    >= experiment.snapshot["request"]["concurrency"]
                ):
                    continue
            work.status = "claimed"
            work.runner_id = runner.id
            work.lease_token = uuid4()
            work.lease_expires_at = now() + timedelta(seconds=settings.lease_seconds)
            work.reserved = True
            run = session.get(CaseRun, work.case_run_id)
            if request.kind == "execute":
                attempt = Attempt(
                    case_run_id=run.id,
                    project_id=project.id,
                    runner_id=runner.id,
                    trace_id=secrets.token_hex(16),
                    root_span_id=secrets.token_hex(8),
                    idempotency_key=str(uuid4()),
                    deadline=now()
                    + timedelta(seconds=experiment.snapshot["request"]["timeout_seconds"]),
                )
                session.add(attempt)
                session.flush()
                work.attempt_id = attempt.id
                run.status = "running"
                case = session.get(CaseVersion, run.case_version_id)
                payload = {
                    "schema_version": "1.0",
                    "experiment_id": experiment.id,
                    "case_run_id": run.id,
                    "attempt_id": attempt.id,
                    "idempotency_key": attempt.idempotency_key,
                    "deadline": attempt.deadline,
                    "traceparent": f"00-{attempt.trace_id}-{attempt.root_span_id}-01",
                    "input": case.content["input"],
                    "environment": case.content["environment"],
                    "artifact_requirements": case.content["artifact_requirements"],
                    "target": target.content,
                }
            else:
                score = session.get(ScoreRun, work.score_run_id)
                score.status = "running"
                score.deadline = now() + timedelta(
                    seconds=session.get(ScorerVersion, score.scorer_id).content["timeout_seconds"]
                )
                payload = ScoreAssignment(
                    score_run_id=score.id,
                    attempt_id=score.attempt_id,
                    manifest_id=score.manifest_id,
                    deadline=score.deadline,
                ).model_dump(mode="json")
            experiment.status = "running"
            session.flush()
            return {
                "schema_version": "1.0",
                "work_item_id": work.id,
                "kind": work.kind,
                "lease_token": work.lease_token,
                "lease_expires_at": work.lease_expires_at,
                "lease_seconds": settings.lease_seconds,
                "payload": payload,
            }
    return None


def lease(
    session: Session,
    credential: Credential,
    work_id: UUID,
    request: LeaseRequest,
    *,
    completion=None,
    read_only=False,
):
    if not read_only:
        scheduling_lock(session)
    runner = authorized_runner(session, credential, request.runner_id)
    work = scoped(session, WorkItem, work_id, credential.project_id, lock=not read_only)
    authorize_work(credential, work)
    if work.runner_id != runner.id:
        raise DomainError(409, "stale_lease", "work belongs to a different Runner")
    if completion is not None and work.completion_digest is not None:
        if work.completed_by == request.lease_token and work.completion_digest == completion:
            return work, True
        raise DomainError(409, "completion_conflict", "work already has a different completion")
    if (
        work.lease_token != request.lease_token
        or work.status != "claimed"
        or (work.lease_expires_at is None or work.lease_expires_at <= now())
    ):
        raise DomainError(409, "stale_lease", "lease expired or was invalidated")
    if not read_only:
        runner.last_seen_at = now()
    return work, False


def score_input(session: Session, credential: Credential, work_id: UUID, request: LeaseRequest):
    # The assigned manifest is immutable. Reading it needs authorization, but must
    # not hold global scheduling locks while materializing large evidence.
    work, _ = lease(session, credential, work_id, request, read_only=True)
    if work.kind != "score":
        raise DomainError(409, "work_kind", "only scoring work has scoring input")
    score = session.get(ScoreRun, work.score_run_id)
    if score.deadline <= now():
        raise DomainError(409, "score_deadline", "score computation deadline has passed")
    return evaluation.score_input(session, score)


def heartbeat(
    session: Session,
    credential: Credential,
    work_id: UUID,
    request: LeaseRequest,
    settings: Settings,
):
    work, _ = lease(session, credential, work_id, request)
    work.lease_expires_at = now() + timedelta(seconds=settings.lease_seconds)
    attempt = session.get(Attempt, work.attempt_id)
    stop_requested = (
        attempt.status == "cancel_requested" or attempt.deadline <= now()
        if work.kind == "execute"
        else (
            session.get(ScoreRun, work.score_run_id).deadline <= now()
            or session.get(ScoreRun, work.score_run_id).cancel_requested_at is not None
        )
    )
    return {
        "schema_version": "1.0",
        "lease_expires_at": work.lease_expires_at,
        "cancel_requested": stop_requested,
    }


def progress(
    session: Session,
    credential: Credential,
    work_id: UUID,
    request: LeaseRequest,
    update: ExecutionProgress,
):
    work, _ = lease(session, credential, work_id, request)
    if work.kind != "execute":
        raise DomainError(409, "work_kind", "only execution work has execution progress")
    attempt = session.get(Attempt, work.attempt_id)
    if attempt.status == "cancel_requested" or attempt.deadline <= now():
        raise DomainError(409, "stop_required", "cancellation or deadline prevents new execution")
    allowed = {
        "claimed": {"preparing"},
        "preparing": {"preparing", "running"},
        "running": {"running"},
    }
    if update.state not in allowed.get(attempt.status, set()):
        raise DomainError(409, "state_transition", "execution state transition is not allowed")
    attempt.status = update.state
    if update.state == "running" and attempt.execution_intent_at is None:
        attempt.execution_intent_at = now()
    if update.remote_operation_id is not None:
        attempt.remote_operation_id = update.remote_operation_id
    session.flush()
    return {"schema_version": "1.0", "attempt_id": attempt.id, "status": attempt.status}


def refresh_experiment(session: Session, experiment_id: UUID):
    session.flush()
    experiment = session.get(Experiment, experiment_id)
    states = session.scalars(
        select(WorkItem.status).where(WorkItem.experiment_id == experiment_id)
    ).all()
    waiting = session.scalar(
        select(EvidenceWait.id)
        .join(Attempt)
        .join(CaseRun)
        .where(CaseRun.experiment_id == experiment_id, EvidenceWait.status == "waiting")
        .limit(1)
    )
    if waiting or any(state in {"queued", "claimed"} for state in states):
        if experiment.status != "cancel_requested":
            experiment.status = "running" if waiting or "claimed" in states else "queued"
    else:
        experiment.status = "completed_with_unresolved" if "unknown" in states else "completed"


def finish(
    session: Session,
    credential: Credential,
    work_id: UUID,
    request: LeaseRequest,
    result: ExecutionResult | ScoreOutput,
    store: evidence.ArtifactStore,
    settings: Settings,
):
    sanitized = evidence.redact(result.model_dump(mode="json"))
    completion = digest(result.model_dump(mode="json"))
    work, duplicate = lease(session, credential, work_id, request, completion=completion)
    if duplicate:
        return {
            "schema_version": "1.0",
            "work_item_id": work.id,
            "status": work.status,
            "duplicate": True,
        }
    if work.kind == "execute" and isinstance(result, ExecutionResult):
        attempt = scoped(session, Attempt, work.attempt_id, credential.project_id, lock=True)
        if result.status == "succeeded" and attempt.execution_intent_at is None:
            raise DomainError(
                409, "missing_execution_intent", "mark running before invoking the target"
            )
        attempt.status = result.status
        attempt.result = sanitized
        attempt.finished_at = now()
        attempt.remote_operation_id = result.remote_operation_id or attempt.remote_operation_id
        attempt.cleanup_status = result.cleanup_status
        attempt.evidence_status = result.evidence_status
        run = session.get(CaseRun, work.case_run_id)
        run.status = result.status
        manifest = evidence.seal(session, attempt)
        if result.status == "succeeded":
            evaluation.enqueue(
                session,
                attempt,
                manifest,
                allow_wait=session.get(Experiment, work.experiment_id).status != "cancel_requested",
                skipped=session.get(Experiment, work.experiment_id).status == "cancel_requested",
            )
        work.status = "unknown" if result.status == "unknown" else "completed"
        work.reserved = result.status == "unknown"
    elif work.kind == "score" and isinstance(result, ScoreOutput):
        score = session.get(ScoreRun, work.score_run_id)
        if score.deadline + timedelta(seconds=settings.score_submission_grace_seconds) <= now():
            raise DomainError(409, "score_submission_deadline", "score submission window has ended")
        if result.status == "completed" and (result.completed_at or now()) > score.deadline:
            raise DomainError(
                409, "score_deadline", "scoring completed after its computation deadline"
            )
        if score.cancel_requested_at:
            result = ScoreOutput(
                status="skipped", reason="scoring cancelled", completed_at=result.completed_at
            )
        evaluation.complete(session, score, result, store)
        work.status = "completed"
        work.reserved = False
    else:
        raise DomainError(409, "work_kind", "completion payload does not match work kind")
    work.completion_digest = completion
    work.completed_by = work.lease_token
    work.lease_token = None
    work.lease_expires_at = None
    refresh_experiment(session, work.experiment_id)
    return {
        "schema_version": "1.0",
        "work_item_id": work.id,
        "status": work.status,
        "duplicate": False,
    }


def cancel(session: Session, project_id: UUID, experiment_id: UUID):
    scheduling_lock(session)
    experiment = scoped(session, Experiment, experiment_id, project_id, lock=True)
    if experiment.status in {"completed", "completed_with_unresolved"}:
        return experiment
    experiment.status = "cancel_requested"
    for work in session.scalars(
        select(WorkItem)
        .where(WorkItem.experiment_id == experiment.id, WorkItem.kind == "execute")
        .with_for_update()
    ):
        if work.status == "queued":
            work.status = "cancelled"
            session.get(CaseRun, work.case_run_id).status = "cancelled"
        elif work.status == "claimed":
            attempt = session.get(Attempt, work.attempt_id)
            if attempt.status != "cancel_requested":
                attempt.status = "cancel_requested"
                attempt.cancel_requested_at = now()
    evaluation.advance_waits(session, experiment_id=experiment.id, cancel=True)
    for work in session.scalars(
        select(WorkItem)
        .where(
            WorkItem.experiment_id == experiment.id,
            WorkItem.kind == "score",
            WorkItem.status.in_(["queued", "claimed"]),
        )
        .with_for_update()
    ):
        score = session.get(ScoreRun, work.score_run_id)
        if work.status == "queued":
            score.status = "skipped"
            score.result = ScoreOutput(status="skipped", reason="experiment cancelled").model_dump(
                mode="json"
            )
            work.status = "cancelled"
        elif score.cancel_requested_at is None:
            score.cancel_requested_at = now()
    refresh_experiment(session, experiment.id)
    return experiment


def resolve(session: Session, credential: Credential, attempt_id: UUID, resolution: Resolution):
    scheduling_lock(session)
    attempt = scoped(session, Attempt, attempt_id, credential.project_id, lock=True)
    if attempt.status not in {"unknown", "cancel_requested"}:
        raise DomainError(409, "not_unresolved", "only unresolved execution can be reconciled")
    if resolution.status == "succeeded" and resolution.output is None:
        raise DomainError(422, "missing_output", "successful reconciliation requires output")
    work = session.scalar(
        select(WorkItem)
        .where(WorkItem.attempt_id == attempt_id, WorkItem.kind == "execute")
        .with_for_update()
    )
    session.add(
        ResolutionRecord(
            attempt_id=attempt_id,
            credential_id=credential.id,
            previous_status=attempt.status,
            content=evidence.redact(resolution.model_dump(mode="json")),
        )
    )
    attempt.status = resolution.status
    attempt.finished_at = now()
    attempt.evidence_status = "partial"
    # The original submission remains in ResolutionRecord/previous result. Explicit
    # reconciliation is a new sourced fact, never an automatic lease-expiry success.
    previous_result = attempt.result
    attempt.result = {
        "schema_version": "1.0",
        "status": resolution.status,
        "output": evidence.redact(resolution.output),
        "error": resolution.reason,
        "previous_result": previous_result,
        "source": "manager_reconciliation",
    }
    session.get(CaseRun, attempt.case_run_id).status = resolution.status
    work.status = "completed"
    work.reserved = False
    work.lease_token = None
    work.lease_expires_at = None
    manifest = evidence.seal(session, attempt)
    if resolution.status == "succeeded":
        evaluation.enqueue(
            session,
            attempt,
            manifest,
            allow_wait=session.get(Experiment, work.experiment_id).status != "cancel_requested",
            skipped=session.get(Experiment, work.experiment_id).status == "cancel_requested",
        )
    refresh_experiment(session, work.experiment_id)
    return attempt


def sweep(session: Session, settings: Settings):
    scheduling_lock(session)
    current_time = now()
    changed = set()
    counts = {"safe_requeued": 0, "unknown": 0, "score_errors": 0, "stop_requested": 0}
    works = session.scalars(
        select(WorkItem).where(WorkItem.status == "claimed").with_for_update(skip_locked=True)
    ).all()
    for work in works:
        expired = work.lease_expires_at <= current_time
        if work.kind == "score":
            score = session.get(ScoreRun, work.score_run_id)
            submission_deadline = score.deadline + timedelta(
                seconds=settings.score_submission_grace_seconds
            )
            cancelled = (
                score.cancel_requested_at
                and score.cancel_requested_at
                + timedelta(seconds=settings.cancellation_grace_seconds)
                <= current_time
            )
            if expired or submission_deadline <= current_time or cancelled:
                score.status = "error"
                score.result = ScoreOutput(
                    status="error", reason="score lease lost or submission window ended"
                ).model_dump(mode="json")
                work.status = "completed"
                work.reserved = False
                work.lease_token = None
                counts["score_errors"] += 1
                changed.add(work.experiment_id)
            continue
        attempt = session.scalar(
            select(Attempt).where(Attempt.id == work.attempt_id).with_for_update()
        )
        if expired:
            work.lease_token = None
            if attempt.execution_intent_at is None:
                cancelled = attempt.status == "cancel_requested" or attempt.deadline <= current_time
                attempt.status = "cancelled" if cancelled else "failed"
                attempt.finished_at = current_time
                attempt.cleanup_status = "unknown"
                attempt.evidence_status = "partial"
                attempt.result = {
                    "schema_version": "1.0",
                    "status": attempt.status,
                    "error": "lease lost before recorded execution intent",
                    "output": None,
                    "source": "scheduler",
                }
                evidence.seal(session, attempt)
                work.status = "completed"
                work.reserved = False
                run = session.get(CaseRun, work.case_run_id)
                attempt_count = session.scalar(
                    select(func.count()).select_from(Attempt).where(Attempt.case_run_id == run.id)
                )
                retry_allowed = not cancelled and attempt_count < settings.max_preparation_attempts
                run.status = "cancelled" if cancelled else "queued" if retry_allowed else "failed"
                if retry_allowed:
                    session.add(
                        WorkItem(
                            project_id=work.project_id,
                            experiment_id=work.experiment_id,
                            target_id=work.target_id,
                            target_scope_id=work.target_scope_id,
                            case_run_id=work.case_run_id,
                            kind="execute",
                            plugin=work.plugin,
                        )
                    )
                    counts["safe_requeued"] += 1
            else:
                mark_unknown(
                    session, work, attempt, "execution lease lost; external result unknown"
                )
                counts["unknown"] += 1
            changed.add(work.experiment_id)
        elif attempt.deadline <= current_time and attempt.status != "cancel_requested":
            attempt.status = "cancel_requested"
            attempt.cancel_requested_at = current_time
            counts["stop_requested"] += 1
        elif (
            attempt.cancel_requested_at
            and attempt.cancel_requested_at + timedelta(seconds=settings.cancellation_grace_seconds)
            <= current_time
        ):
            mark_unknown(session, work, attempt, "stop request was not confirmed")
            counts["unknown"] += 1
            changed.add(work.experiment_id)
    changed.update(evaluation.advance_waits(session))
    for experiment_id in changed:
        refresh_experiment(session, experiment_id)
    session.flush()
    return counts


def mark_unknown(session: Session, work: WorkItem, attempt: Attempt, reason: str):
    attempt.status = "unknown"
    attempt.cleanup_status = "unknown"
    attempt.evidence_status = "partial"
    attempt.result = {
        "schema_version": "1.0",
        "status": "unknown",
        "output": None,
        "error": reason,
        "source": "scheduler",
    }
    session.get(CaseRun, attempt.case_run_id).status = "unknown"
    work.status = "unknown"
    work.lease_token = None
    work.lease_expires_at = None
    # Keep work.reserved: external effects may still be running.
    evidence.seal(session, attempt)
