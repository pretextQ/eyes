import hashlib
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import select

from eyes.contracts.observation import ObservationBatch, ObservationSourceCreate
from eyes.server.api.dependencies import Database, Manager, Reader, bearer
from eyes.server.domain import DomainError, public_record, scoped
from eyes.server.observation import service
from eyes.server.observation.local import LocalIdentity
from eyes.server.storage.models import ObservationSource, ObservedEvent, ObservedRun

router = APIRouter(prefix="/v1/observation", tags=["observation"])
Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=1000000)]


def source_identity(
    session: Database, supplied: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
):
    if supplied is None:
        raise DomainError(401, "authentication_required", "observation token required")
    source = session.scalar(
        select(ObservationSource).where(
            ObservationSource.token_digest
            == hashlib.sha256(supplied.credentials.encode()).hexdigest(),
            ObservationSource.revoked.is_(False),
        )
    )
    if source is None:
        raise DomainError(401, "invalid_token", "observation token is invalid or revoked")
    return source, supplied.credentials


SourceIdentity = Annotated[tuple, Depends(source_identity)]


@router.post("/sources", status_code=201)
def create_source(body: ObservationSourceCreate, session: Database, user: Manager):
    return {"schema_version": "1.0", **service.create_source(session, user.project_id, body)}


@router.get("/sources")
def sources(session: Database, user: Reader, limit: Limit = 50, offset: Offset = 0):
    return {
        "schema_version": "1.0",
        "items": [
            public_record(source)
            for source in session.scalars(
                select(ObservationSource)
                .where(ObservationSource.project_id == user.project_id)
                .order_by(ObservationSource.created_at.desc(), ObservationSource.id)
                .limit(limit)
                .offset(offset)
            )
        ],
    }


@router.post("/sources/{source_id}/revoke")
def revoke_source(source_id: UUID, session: Database, user: Manager):
    source = scoped(session, ObservationSource, source_id, user.project_id, lock=True)
    source.revoked = True
    return {"schema_version": "1.0", **public_record(source)}


@router.post("/events")
def ingest(body: ObservationBatch, session: Database, identity: SourceIdentity):
    return service.ingest(session, identity[0], body, identity[1])


@router.post("/heartbeat")
def heartbeat(run_id: str, session: Database, identity: SourceIdentity):
    source, _ = identity
    # Serialize with revoke/ingest so a revoked producer cannot refresh liveness.
    source = session.scalar(
        select(ObservationSource)
        .where(ObservationSource.id == source.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if source.revoked:
        raise DomainError(401, "invalid_token", "observation token was revoked")
    source.last_seen_at = datetime.now(UTC)
    run = session.scalar(
        select(ObservedRun).where(
            ObservedRun.source_id == source.id, ObservedRun.external_id == run_id
        )
    )
    if run and run.status == "running":
        run.last_seen_at = source.last_seen_at
    return {"schema_version": "1.0", "accepted": run is not None}


@router.get("/runs")
def runs(
    session: Database,
    user: Reader,
    limit: Limit = 50,
    offset: Offset = 0,
    source_id: UUID | None = None,
    session_id: str | None = None,
):
    query = select(ObservedRun).where(ObservedRun.project_id == user.project_id)
    if source_id:
        query = query.where(ObservedRun.source_id == source_id)
    if session_id:
        query = query.where(ObservedRun.session_id == session_id)
    values = session.scalars(
        query.order_by(ObservedRun.created_at.desc(), ObservedRun.id).limit(limit).offset(offset)
    )
    return {"schema_version": "1.0", "items": [service.summary(run) for run in values]}


@router.get("/runs/{run_id}")
def run_detail(
    run_id: UUID, session: Database, user: Reader, limit: Limit = 200, offset: Offset = 0
):
    run = scoped(session, ObservedRun, run_id, user.project_id)
    events = session.scalars(
        select(ObservedEvent)
        .where(ObservedEvent.run_id == run.id)
        .order_by(ObservedEvent.sequence)
        .limit(limit)
        .offset(offset)
    ).all()
    return {
        "schema_version": "1.0",
        **service.summary(run),
        "events": [public_record(event) for event in events],
        "has_more": offset + len(events) < run.metrics.get("events", 0),
    }


@router.post("/local/events")
def local_ingest(body: ObservationBatch, session: Database, identity: LocalIdentity):
    return service.ingest(session, identity[0], body, identity[1])


@router.post("/local/heartbeat")
def local_heartbeat(run_id: str, session: Database, identity: LocalIdentity):
    return heartbeat(run_id, session, identity)
