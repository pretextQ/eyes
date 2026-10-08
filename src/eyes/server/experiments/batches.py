"""Atomic multi-Agent batches; each member retains the normal experiment lifecycle."""

from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from eyes.contracts.work import ExperimentBatchCreate
from eyes.server.config import Settings
from eyes.server.domain import DomainError, digest, public_record, scoped
from eyes.server.experiments import service as experiments
from eyes.server.scheduling import service as scheduling
from eyes.server.storage.models import (
    CaseRun,
    CaseVersion,
    DatasetVersion,
    Experiment,
    ExperimentBatch,
    Project,
    WorkItem,
)

TERMINAL = {"completed", "completed_with_unresolved"}


def create(
    session: Session, project_id: UUID, key: str, request: ExperimentBatchCreate, settings: Settings
):
    # All members and their work commit in the API's single transaction. Replaying
    # a key after a timeout returns that same batch, including its original members.
    session.scalar(select(Project).where(Project.id == project_id).with_for_update())
    content = request.model_dump(mode="json")
    request_digest = digest(content)
    previous = session.scalar(
        select(ExperimentBatch).where(
            ExperimentBatch.project_id == project_id, ExperimentBatch.request_key == key
        )
    )
    if previous:
        if previous.request_digest != request_digest:
            raise DomainError(409, "idempotency_conflict", "same key has different parameters")
        return previous
    # Bound aggregate fan-out, not just each member, before allocating any work.
    case_counts = dict(
        session.execute(
            select(CaseVersion.dataset_id, func.count())
            .join(DatasetVersion, DatasetVersion.id == CaseVersion.dataset_id)
            .where(DatasetVersion.project_id == project_id)
            .where(CaseVersion.dataset_id.in_([e.dataset_version_id for e in request.experiments]))
            .group_by(CaseVersion.dataset_id)
        ).all()
    )
    total = sum(
        case_counts.get(e.dataset_version_id, 0) * e.repetitions for e in request.experiments
    )
    if total > settings.max_experiment_runs:
        raise DomainError(413, "too_many_runs", "batch exceeds configured aggregate run limit")
    batch = ExperimentBatch(
        project_id=project_id,
        name=request.name,
        request_key=key,
        request_digest=request_digest,
        snapshot={"schema_version": "1.0", "request": content},
    )
    session.add(batch)
    session.flush()
    for index, member in enumerate(request.experiments):
        experiment = experiments.create(
            session, project_id, f"batch:{batch.id}:{index}", member, settings
        )
        experiment.batch_id = batch.id
    session.flush()
    return batch


def status(members):
    states = {member.status for member in members}
    if states and states <= TERMINAL:
        return "completed_with_unresolved" if "completed_with_unresolved" in states else "completed"
    # Cancelling one member must not disable batch cancellation for its siblings.
    if states - TERMINAL == {"cancel_requested"}:
        return "cancel_requested"
    return "running" if states - {"queued"} else "queued"


def list_batches(session: Session, project_id: UUID, limit: int, offset: int):
    batches = session.scalars(
        select(ExperimentBatch)
        .where(ExperimentBatch.project_id == project_id)
        .order_by(ExperimentBatch.created_at.desc(), ExperimentBatch.id)
        .limit(limit)
        .offset(offset)
    ).all()
    members = defaultdict(list)
    for member in session.scalars(
        select(Experiment).where(Experiment.batch_id.in_([batch.id for batch in batches]))
    ):
        members[member.batch_id].append(member)
    return [
        {
            "id": batch.id,
            "created_at": batch.created_at,
            "name": batch.name,
            "status": status(members[batch.id]),
            "agent_count": len(members[batch.id]),
            "requested_concurrency": sum(
                e.snapshot["request"]["concurrency"] for e in members[batch.id]
            ),
        }
        for batch in batches
    ]


def detail(session: Session, batch: ExperimentBatch):
    members = session.scalars(
        select(Experiment)
        .where(Experiment.batch_id == batch.id)
        .order_by(Experiment.created_at, Experiment.id)
    ).all()
    ids = [member.id for member in members]
    dataset_names = dict(
        session.execute(
            select(DatasetVersion.id, DatasetVersion.name).where(
                DatasetVersion.id.in_([member.dataset_id for member in members])
            )
        ).all()
    )
    counts = defaultdict(dict)
    for experiment_id, run_status, count in session.execute(
        select(CaseRun.experiment_id, CaseRun.status, func.count())
        .where(CaseRun.experiment_id.in_(ids))
        .group_by(CaseRun.experiment_id, CaseRun.status)
    ):
        counts[experiment_id][run_status] = count
    reserved = dict(
        session.execute(
            select(WorkItem.experiment_id, func.count())
            .where(
                WorkItem.experiment_id.in_(ids),
                WorkItem.kind == "execute",
                WorkItem.reserved.is_(True),
            )
            .group_by(WorkItem.experiment_id)
        ).all()
    )
    result = []
    for member in members:
        runs = counts[member.id]
        result.append(
            {
                **public_record(member),
                "dataset_name": dataset_names[member.dataset_id],
                "progress": {
                    "planned": sum(runs.values()),
                    "states": runs,
                    "reserved": reserved.get(member.id, 0),
                },
            }
        )
    return {
        "schema_version": "1.0",
        **public_record(batch),
        "status": status(members),
        "members": result,
    }


def cancel(session: Session, project_id: UUID, batch_id: UUID):
    batch = scoped(session, ExperimentBatch, batch_id, project_id)
    ids = session.scalars(
        select(Experiment.id).where(Experiment.batch_id == batch.id).order_by(Experiment.id)
    ).all()
    for experiment_id in ids:
        scheduling.cancel(session, project_id, experiment_id)
    return batch
