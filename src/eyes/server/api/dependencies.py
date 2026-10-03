import hashlib
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from eyes.server.domain import DomainError
from eyes.server.storage.models import Credential

bearer = HTTPBearer(auto_error=False)


def db_session(request: Request):
    try:
        with request.app.state.sessions() as session, session.begin():
            # Acquire only when a database transaction actually starts. Requests
            # missing a bearer token can still fail with 401 while DB is offline.
            event.listen(
                session,
                "after_begin",
                lambda session, transaction, connection: connection.exec_driver_sql(
                    "SELECT pg_advisory_xact_lock_shared(74000)"
                ),
            )
            yield session
    except OperationalError as exc:
        raise DomainError(503, "database_unavailable", "database is not available") from exc


Database = Annotated[Session, Depends(db_session, scope="function")]


def identity(
    session: Database, supplied: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]
):
    if supplied is None:
        raise DomainError(401, "authentication_required", "Bearer token required")
    token_digest = hashlib.sha256(supplied.credentials.encode()).hexdigest()
    credential = session.scalar(
        select(Credential).where(
            Credential.token_digest == token_digest, Credential.revoked.is_(False)
        )
    )
    if credential is None:
        raise DomainError(401, "invalid_token", "token is invalid or revoked")
    return credential


def roles(*allowed):
    def authorize(credential: Annotated[Credential, Depends(identity)]):
        if credential.role not in allowed:
            raise DomainError(
                403, "permission_denied", "credential does not authorize this operation"
            )
        return credential

    return authorize


Reader = Annotated[Credential, Depends(roles("read", "manage"))]
Manager = Annotated[Credential, Depends(roles("manage"))]
RunnerIdentity = Annotated[Credential, Depends(roles("runner"))]
ArtifactReader = Annotated[Credential, Depends(roles("read", "manage", "runner"))]
