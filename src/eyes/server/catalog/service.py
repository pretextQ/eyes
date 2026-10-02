import json
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from eyes.contracts.base import SENSITIVE_KEYS
from eyes.contracts.dataset import CaseDefinition, DatasetImport
from eyes.contracts.scorer import ScorerPublish
from eyes.contracts.target import TargetPublish
from eyes.server.config import Settings
from eyes.server.domain import DomainError, digest
from eyes.server.storage.models import (
    CaseVersion,
    DatasetVersion,
    Project,
    ScorerVersion,
    Target,
    TargetVersion,
)


def reject_inline_secrets(value, path="config"):
    if isinstance(value, dict):
        for key, child in value.items():
            if key.lower().replace("-", "_") in SENSITIVE_KEYS:
                raise DomainError(422, "inline_secret", f"{path}.{key}: use secret_refs")
            reject_inline_secrets(child, f"{path}.{key}")
    elif isinstance(value, list):
        for child in value:
            reject_inline_secrets(child, path)
    elif isinstance(value, str) and value.startswith(("http://", "https://")):
        try:
            url = urlsplit(value)
        except ValueError as exc:
            raise DomainError(422, "invalid_url", f"{path}: URL is invalid") from exc
        if (
            url.username
            or url.password
            or any(
                key.lower().replace("-", "_") in SENSITIVE_KEYS for key, _ in parse_qsl(url.query)
            )
        ):
            raise DomainError(422, "inline_secret", f"{path}: URL credentials must use secret_refs")


def publish(session: Session, project_id: UUID, request: TargetPublish | ScorerPublish):
    reject_inline_secrets(request.config)
    content = request.model_dump(mode="json")
    model = TargetVersion if isinstance(request, TargetPublish) else ScorerVersion
    fields = {
        "project_id": project_id,
        "name": request.name,
        "digest": digest(content),
        "content": content,
    }
    if isinstance(request, TargetPublish):
        session.scalar(select(Project).where(Project.id == project_id).with_for_update())
        target = session.scalar(
            select(Target).where(
                Target.project_id == project_id,
                Target.name == request.name,
            )
        )
        if target is None:
            target = Target(
                project_id=project_id,
                name=request.name,
                concurrency_limit=request.concurrency_limit,
            )
            session.add(target)
            session.flush()
        elif target.concurrency_limit != request.concurrency_limit:
            raise DomainError(
                409, "target_limit_change", "published versions share a fixed target capacity"
            )
        fields["target_id"] = target.id
    version = model(**fields)
    session.add(version)
    session.flush()
    return version


def import_dataset(session: Session, project_id: UUID, request: DatasetImport, settings: Settings):
    cases = []
    errors = []
    identifiers = set()
    lines = request.jsonl.splitlines()
    if len(lines) > settings.max_dataset_cases:
        raise DomainError(413, "too_many_cases", "dataset exceeds the configured case limit")
    for line_number, line in enumerate(lines, 1):
        try:
            case = CaseDefinition.model_validate_json(line)
            if case.case_id in identifiers:
                errors.append({"line": line_number, "message": "duplicate case_id"})
            identifiers.add(case.case_id)
            cases.append(case.model_dump(mode="json"))
        except ValidationError as exc:
            errors.append(
                {
                    "line": line_number,
                    "errors": json.loads(exc.json(include_input=False, include_context=False)),
                }
            )
    if errors:
        raise DomainError(422, "invalid_dataset", "dataset was not published", errors)
    if not cases:
        raise DomainError(422, "empty_dataset", "at least one case is required")
    content = {"schema_version": "1.0", "cases": cases}
    version = DatasetVersion(
        project_id=project_id, name=request.name, digest=digest(content), content=content
    )
    session.add(version)
    session.flush()
    session.add_all(
        [
            CaseVersion(
                dataset_id=version.id, case_id=case["case_id"], digest=digest(case), content=case
            )
            for case in cases
        ]
    )
    session.flush()
    return version


def list_versions(session: Session, project_id: UUID, model, limit: int, offset: int):
    return session.scalars(
        select(model)
        .where(model.project_id == project_id)
        .order_by(model.created_at.desc(), model.id)
        .limit(limit)
        .offset(offset)
    ).all()
