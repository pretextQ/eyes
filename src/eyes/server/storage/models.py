from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class Record(Base):
    __abstract__ = True
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Project(Record):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("execution_limit > 0 AND score_limit > 0", name="ck_project_limits"),
    )
    name: Mapped[str] = mapped_column(String(200))
    execution_limit: Mapped[int] = mapped_column(default=8)
    score_limit: Mapped[int] = mapped_column(default=2)


class Credential(Record):
    __tablename__ = "credentials"
    __table_args__ = (
        CheckConstraint("role IN ('read', 'manage', 'runner')", name="ck_credential_role"),
    )
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    token_digest: Mapped[str] = mapped_column(String(64), unique=True)
    role: Mapped[str] = mapped_column(String(20))
    target_ids: Mapped[list] = mapped_column(JSONB, default=list)
    work_kinds: Mapped[list] = mapped_column(JSONB, default=list)
    revoked: Mapped[bool] = mapped_column(default=False)


class Version(Record):
    __abstract__ = True
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    digest: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSONB)


class Target(Record):
    __tablename__ = "targets"
    __table_args__ = (
        UniqueConstraint("project_id", "name"),
        CheckConstraint("concurrency_limit > 0", name="ck_target_limit"),
    )
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    concurrency_limit: Mapped[int]


class TargetVersion(Version):
    __tablename__ = "target_versions"
    target_id: Mapped[UUID] = mapped_column(ForeignKey("targets.id"), index=True)


class DatasetVersion(Version):
    __tablename__ = "dataset_versions"


class ScorerVersion(Version):
    __tablename__ = "scorer_versions"


class CaseVersion(Record):
    __tablename__ = "case_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "case_id"),)
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_versions.id"), index=True)
    case_id: Mapped[str] = mapped_column(String(200))
    digest: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSONB)


class Experiment(Record):
    __tablename__ = "experiments"
    __table_args__ = (UniqueConstraint("project_id", "request_key"),)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    target_id: Mapped[UUID] = mapped_column(ForeignKey("target_versions.id"))
    target_scope_id: Mapped[UUID] = mapped_column(ForeignKey("targets.id"))
    dataset_id: Mapped[UUID] = mapped_column(ForeignKey("dataset_versions.id"))
    request_key: Mapped[str] = mapped_column(String(200))
    request_digest: Mapped[str] = mapped_column(String(64))
    snapshot: Mapped[dict] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(30), default="queued")


class CaseRun(Record):
    __tablename__ = "case_runs"
    __table_args__ = (UniqueConstraint("experiment_id", "case_version_id", "repetition"),)
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id"), index=True)
    case_version_id: Mapped[UUID] = mapped_column(ForeignKey("case_versions.id"))
    repetition: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30), default="queued")


class Runner(Record):
    __tablename__ = "runners"
    credential_id: Mapped[UUID] = mapped_column(ForeignKey("credentials.id"), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    capabilities: Mapped[dict] = mapped_column(JSONB)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Attempt(Record):
    __tablename__ = "attempts"
    case_run_id: Mapped[UUID] = mapped_column(ForeignKey("case_runs.id"), index=True)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    runner_id: Mapped[UUID] = mapped_column(ForeignKey("runners.id"))
    trace_id: Mapped[str] = mapped_column(String(32))
    root_span_id: Mapped[str] = mapped_column(String(16))
    idempotency_key: Mapped[str] = mapped_column(String(64), unique=True)
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="claimed")
    execution_intent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    remote_operation_id: Mapped[str | None] = mapped_column(String(500))
    cleanup_status: Mapped[str] = mapped_column(String(30), default="pending")
    evidence_status: Mapped[str] = mapped_column(String(30), default="collecting")
    result: Mapped[dict | None] = mapped_column(JSONB)
    evidence_expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Manifest(Record):
    __tablename__ = "evidence_manifests"
    __table_args__ = (UniqueConstraint("attempt_id", "version"),)
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id"), index=True)
    version: Mapped[int]
    content: Mapped[dict] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScoreRun(Record):
    __tablename__ = "score_runs"
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id"), index=True)
    scorer_id: Mapped[UUID] = mapped_column(ForeignKey("scorer_versions.id"))
    manifest_id: Mapped[UUID] = mapped_column(ForeignKey("evidence_manifests.id"))
    trace_id: Mapped[str] = mapped_column(String(32))
    root_span_id: Mapped[str] = mapped_column(String(16))
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    result: Mapped[dict | None] = mapped_column(JSONB)
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WorkItem(Record):
    __tablename__ = "work_items"
    __table_args__ = (
        CheckConstraint("kind IN ('execute', 'score')", name="ck_work_kind"),
        CheckConstraint(
            "(kind = 'execute' AND score_run_id IS NULL) OR "
            "(kind = 'score' AND score_run_id IS NOT NULL AND attempt_id IS NOT NULL)",
            name="ck_work_subject",
        ),
        CheckConstraint(
            "NOT reserved OR status IN ('claimed', 'unknown')", name="ck_work_reservation"
        ),
        CheckConstraint(
            "status <> 'claimed' OR (runner_id IS NOT NULL AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL AND reserved)",
            name="ck_work_claimed_lease",
        ),
        Index("ix_work_queue", "project_id", "kind", "status", "created_at", "id"),
        Index("ix_work_reservations", "kind", "reserved", "target_scope_id", "experiment_id"),
    )
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    experiment_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id"))
    target_id: Mapped[UUID] = mapped_column(ForeignKey("target_versions.id"))
    case_run_id: Mapped[UUID] = mapped_column(ForeignKey("case_runs.id"))
    target_scope_id: Mapped[UUID] = mapped_column(ForeignKey("targets.id"))
    attempt_id: Mapped[UUID | None] = mapped_column(ForeignKey("attempts.id"))
    score_run_id: Mapped[UUID | None] = mapped_column(ForeignKey("score_runs.id"))
    kind: Mapped[str] = mapped_column(String(20))
    plugin: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    runner_id: Mapped[UUID | None] = mapped_column(ForeignKey("runners.id"))
    lease_token: Mapped[UUID | None]
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reserved: Mapped[bool] = mapped_column(default=False)
    completion_digest: Mapped[str | None] = mapped_column(String(64))
    completed_by: Mapped[UUID | None]


class Event(Record):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("project_id", "producer_id", "event_id"),)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id"), index=True)
    producer_id: Mapped[str] = mapped_column(String(200))
    event_id: Mapped[UUID]
    digest: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSONB)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Artifact(Record):
    __tablename__ = "artifacts"
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"))
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id"), index=True)
    metadata_content: Mapped[dict] = mapped_column(JSONB)
    storage_key: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="pending")


class ResolutionRecord(Record):
    __tablename__ = "resolutions"
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id"), index=True)
    credential_id: Mapped[UUID] = mapped_column(ForeignKey("credentials.id"))
    previous_status: Mapped[str] = mapped_column(String(30))
    content: Mapped[dict] = mapped_column(JSONB)


class EvidenceWait(Record):
    __tablename__ = "evidence_waits"
    __table_args__ = (UniqueConstraint("attempt_id", "scorer_id"),)
    attempt_id: Mapped[UUID] = mapped_column(ForeignKey("attempts.id"), index=True)
    scorer_id: Mapped[UUID] = mapped_column(ForeignKey("scorer_versions.id"))
    deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(30), default="waiting")


class ComparisonReport(Record):
    __tablename__ = "comparison_reports"
    __table_args__ = (UniqueConstraint("project_id", "request_key"),)
    project_id: Mapped[UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    baseline_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id"))
    candidate_id: Mapped[UUID] = mapped_column(ForeignKey("experiments.id"))
    request_key: Mapped[str] = mapped_column(String(200))
    request_digest: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSONB)
    digest: Mapped[str] = mapped_column(String(64))
