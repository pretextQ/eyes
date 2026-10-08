"""Direct loopback ingestion; never grants project read or management access."""

import hashlib
from ipaddress import ip_address
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, Request
from sqlalchemy import select, text

from eyes.server.api.dependencies import Database
from eyes.server.domain import DomainError
from eyes.server.storage.models import ObservationSource, Project


def local_identity(
    request: Request,
    session: Database,
    source_id: Annotated[UUID, Header(alias="X-Eyes-Local-Source")],
):
    settings = request.app.state.settings
    try:
        loopback = request.client is not None and ip_address(request.client.host).is_loopback
    except ValueError:
        loopback = False
    if (
        not settings.local_observation
        or not loopback
        or request.url.hostname not in {"127.0.0.1", "localhost", "::1"}
        or any(
            name in request.headers
            for name in (
                "origin",
                "forwarded",
                "x-forwarded-for",
                "x-forwarded-host",
                "x-forwarded-proto",
            )
        )
    ):
        raise DomainError(
            403, "local_only", "local observation requires a direct loopback connection"
        )
    if settings.local_observation_project_id:
        project = session.get(Project, settings.local_observation_project_id)
    else:
        projects = session.scalars(select(Project).limit(2)).all()
        project = projects[0] if len(projects) == 1 else None
    if project is None:
        raise DomainError(
            409, "local_project_required", "select one local observation project on the server"
        )
    # This identifier is deliberately not a bearer-token digest. A source header
    # is a grouping key, not an authentication credential.
    key = "local:" + hashlib.sha256(f"{project.id}:{source_id}".encode()).hexdigest()[:58]
    session.execute(
        text("SELECT pg_advisory_xact_lock(:key)"),
        {"key": int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], signed=True)},
    )
    source = session.scalar(select(ObservationSource).where(ObservationSource.token_digest == key))
    if source is None:
        source = ObservationSource(
            project_id=project.id, name="Deta · 本机自动接入", token_digest=key
        )
        session.add(source)
        session.flush()
    if source.revoked:
        raise DomainError(403, "source_revoked", "local source has been disabled")
    return source, ""


LocalIdentity = Annotated[tuple, Depends(local_identity)]
