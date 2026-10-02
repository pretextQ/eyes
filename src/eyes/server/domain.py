import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session


class DomainError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        self.status = status
        self.code = code
        self.message = message
        self.details = details


def digest(content) -> str:
    return hashlib.sha256(
        json.dumps(
            content, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def scoped(session: Session, model, record_id: UUID, project_id: UUID, *, lock=False):
    query = select(model).where(model.id == record_id, model.project_id == project_id)
    if lock:
        query = query.with_for_update()
    item = session.scalar(query)
    if item is None:
        raise DomainError(404, "not_found", "record not found in this project")
    return item


def public_record(record):
    return {
        column.name: getattr(record, column.name)
        for column in record.__table__.columns
        if column.name not in {"token_digest", "credential_id", "lease_token"}
    }
