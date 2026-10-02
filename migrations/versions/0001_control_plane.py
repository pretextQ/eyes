"""Initial control plane schema.

Revision ID: 0001_control_plane
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_control_plane"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Frozen initial schema.
    op.create_table(
        "projects",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("execution_limit", sa.Integer(), nullable=False),
        sa.Column("score_limit", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("execution_limit > 0 AND score_limit > 0", name="ck_project_limits"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "credentials",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("token_digest", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("target_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("work_kinds", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("role IN ('read', 'manage', 'runner')", name="ck_credential_role"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_digest"),
    )
    op.create_index(op.f("ix_credentials_project_id"), "credentials", ["project_id"], unique=False)
    op.create_table(
        "dataset_versions",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_dataset_versions_project_id"), "dataset_versions", ["project_id"], unique=False
    )
    op.create_table(
        "scorer_versions",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_scorer_versions_project_id"), "scorer_versions", ["project_id"], unique=False
    )
    op.create_table(
        "targets",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("concurrency_limit", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("concurrency_limit > 0", name="ck_target_limit"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "name"),
    )
    op.create_index(op.f("ix_targets_project_id"), "targets", ["project_id"], unique=False)
    op.create_table(
        "case_versions",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.String(length=200), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["dataset_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "case_id"),
    )
    op.create_index(
        op.f("ix_case_versions_dataset_id"), "case_versions", ["dataset_id"], unique=False
    )
    op.create_table(
        "runners",
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("capabilities", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["credentials.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("credential_id"),
    )
    op.create_table(
        "target_versions",
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["targets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_target_versions_project_id"), "target_versions", ["project_id"], unique=False
    )
    op.create_index(
        op.f("ix_target_versions_target_id"), "target_versions", ["target_id"], unique=False
    )
    op.create_table(
        "experiments",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("target_scope_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("request_key", sa.String(length=200), nullable=False),
        sa.Column("request_digest", sa.String(length=64), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["dataset_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["target_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_scope_id"],
            ["targets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "request_key"),
    )
    op.create_index(op.f("ix_experiments_project_id"), "experiments", ["project_id"], unique=False)
    op.create_table(
        "case_runs",
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("case_version_id", sa.Uuid(), nullable=False),
        sa.Column("repetition", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_version_id"],
            ["case_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("experiment_id", "case_version_id", "repetition"),
    )
    op.create_index(
        op.f("ix_case_runs_experiment_id"), "case_runs", ["experiment_id"], unique=False
    )
    op.create_table(
        "attempts",
        sa.Column("case_run_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("runner_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("root_span_id", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=64), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("execution_intent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remote_operation_id", sa.String(length=500), nullable=True),
        sa.Column("cleanup_status", sa.String(length=30), nullable=False),
        sa.Column("evidence_status", sa.String(length=30), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["case_run_id"],
            ["case_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.ForeignKeyConstraint(
            ["runner_id"],
            ["runners.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_index(op.f("ix_attempts_case_run_id"), "attempts", ["case_run_id"], unique=False)
    op.create_index(op.f("ix_attempts_project_id"), "attempts", ["project_id"], unique=False)
    op.create_table(
        "artifacts",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("metadata_content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("storage_key", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["attempts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_artifacts_attempt_id"), "artifacts", ["attempt_id"], unique=False)
    op.create_table(
        "events",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("producer_id", sa.String(length=200), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["attempts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "producer_id", "event_id"),
    )
    op.create_index(op.f("ix_events_attempt_id"), "events", ["attempt_id"], unique=False)
    op.create_table(
        "evidence_manifests",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["attempts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("attempt_id", "version"),
    )
    op.create_index(
        op.f("ix_evidence_manifests_attempt_id"), "evidence_manifests", ["attempt_id"], unique=False
    )
    op.create_table(
        "resolutions",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("credential_id", sa.Uuid(), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["attempts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["credential_id"],
            ["credentials.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resolutions_attempt_id"), "resolutions", ["attempt_id"], unique=False)
    op.create_table(
        "score_runs",
        sa.Column("attempt_id", sa.Uuid(), nullable=False),
        sa.Column("scorer_id", sa.Uuid(), nullable=False),
        sa.Column("manifest_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.String(length=32), nullable=False),
        sa.Column("root_span_id", sa.String(length=16), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["attempts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["manifest_id"],
            ["evidence_manifests.id"],
        ),
        sa.ForeignKeyConstraint(
            ["scorer_id"],
            ["scorer_versions.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_score_runs_attempt_id"), "score_runs", ["attempt_id"], unique=False)
    op.create_table(
        "work_items",
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("experiment_id", sa.Uuid(), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("case_run_id", sa.Uuid(), nullable=False),
        sa.Column("target_scope_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), nullable=True),
        sa.Column("score_run_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("plugin", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("runner_id", sa.Uuid(), nullable=True),
        sa.Column("lease_token", sa.Uuid(), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reserved", sa.Boolean(), nullable=False),
        sa.Column("completion_digest", sa.String(length=64), nullable=True),
        sa.Column("completed_by", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(kind = 'execute' AND score_run_id IS NULL) OR "
            "(kind = 'score' AND score_run_id IS NOT NULL AND attempt_id IS NOT NULL)",
            name="ck_work_subject",
        ),
        sa.CheckConstraint(
            "NOT reserved OR status IN ('claimed', 'unknown')", name="ck_work_reservation"
        ),
        sa.CheckConstraint("kind IN ('execute', 'score')", name="ck_work_kind"),
        sa.CheckConstraint(
            "status <> 'claimed' OR (runner_id IS NOT NULL AND lease_token IS NOT NULL "
            "AND lease_expires_at IS NOT NULL AND reserved)",
            name="ck_work_claimed_lease",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["attempts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["case_run_id"],
            ["case_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.id"],
        ),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["projects.id"],
        ),
        sa.ForeignKeyConstraint(
            ["runner_id"],
            ["runners.id"],
        ),
        sa.ForeignKeyConstraint(
            ["score_run_id"],
            ["score_runs.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_id"],
            ["target_versions.id"],
        ),
        sa.ForeignKeyConstraint(
            ["target_scope_id"],
            ["targets.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_work_queue",
        "work_items",
        ["project_id", "kind", "status", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_work_reservations",
        "work_items",
        ["kind", "reserved", "target_scope_id", "experiment_id"],
        unique=False,
    )
    op.execute("""
        CREATE FUNCTION eyes_reject_version_update() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'published records are immutable';
        END;
        $$
    """)
    for table in (
        "targets",
        "target_versions",
        "dataset_versions",
        "case_versions",
        "scorer_versions",
        "evidence_manifests",
        "events",
        "resolutions",
    ):
        op.execute(
            f"CREATE TRIGGER immutable_record BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION eyes_reject_version_update()"
        )
    op.execute("""
        CREATE FUNCTION eyes_protect_experiment_snapshot() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF (NEW.id, NEW.project_id, NEW.target_id, NEW.target_scope_id,
                NEW.dataset_id, NEW.request_key,
                NEW.request_digest, NEW.snapshot, NEW.created_at)
                IS DISTINCT FROM
               (OLD.id, OLD.project_id, OLD.target_id, OLD.target_scope_id,
                OLD.dataset_id, OLD.request_key,
                OLD.request_digest, OLD.snapshot, OLD.created_at) THEN
                RAISE EXCEPTION 'experiment configuration is immutable';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER frozen_snapshot BEFORE UPDATE ON experiments
        FOR EACH ROW EXECUTE FUNCTION eyes_protect_experiment_snapshot()
    """)
    op.execute("""
        CREATE FUNCTION eyes_protect_published_score() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.result IS NOT NULL THEN
                RAISE EXCEPTION 'published score is immutable; create a new score run';
            END IF;
            RETURN NEW;
        END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER frozen_score BEFORE UPDATE ON score_runs
        FOR EACH ROW EXECUTE FUNCTION eyes_protect_published_score()
    """)


def downgrade() -> None:
    # Frozen initial schema.
    op.drop_index("ix_work_queue", table_name="work_items")
    op.drop_index("ix_work_reservations", table_name="work_items")
    op.drop_table("work_items")
    op.drop_index(op.f("ix_score_runs_attempt_id"), table_name="score_runs")
    op.drop_table("score_runs")
    op.drop_index(op.f("ix_resolutions_attempt_id"), table_name="resolutions")
    op.drop_table("resolutions")
    op.drop_index(op.f("ix_evidence_manifests_attempt_id"), table_name="evidence_manifests")
    op.drop_table("evidence_manifests")
    op.drop_index(op.f("ix_events_attempt_id"), table_name="events")
    op.drop_table("events")
    op.drop_index(op.f("ix_artifacts_attempt_id"), table_name="artifacts")
    op.drop_table("artifacts")
    op.drop_index(op.f("ix_attempts_case_run_id"), table_name="attempts")
    op.drop_index(op.f("ix_attempts_project_id"), table_name="attempts")
    op.drop_table("attempts")
    op.drop_index(op.f("ix_case_runs_experiment_id"), table_name="case_runs")
    op.drop_table("case_runs")
    op.drop_index(op.f("ix_experiments_project_id"), table_name="experiments")
    op.drop_table("experiments")
    op.drop_index(op.f("ix_target_versions_project_id"), table_name="target_versions")
    op.drop_index(op.f("ix_target_versions_target_id"), table_name="target_versions")
    op.drop_table("target_versions")
    op.drop_table("runners")
    op.drop_index(op.f("ix_case_versions_dataset_id"), table_name="case_versions")
    op.drop_table("case_versions")
    op.drop_index(op.f("ix_targets_project_id"), table_name="targets")
    op.drop_table("targets")
    op.drop_index(op.f("ix_scorer_versions_project_id"), table_name="scorer_versions")
    op.drop_table("scorer_versions")
    op.drop_index(op.f("ix_dataset_versions_project_id"), table_name="dataset_versions")
    op.drop_table("dataset_versions")
    op.drop_index(op.f("ix_credentials_project_id"), table_name="credentials")
    op.drop_table("credentials")
    op.drop_table("projects")
    op.execute("DROP FUNCTION eyes_protect_published_score()")
    op.execute("DROP FUNCTION eyes_protect_experiment_snapshot()")
    op.execute("DROP FUNCTION eyes_reject_version_update()")
