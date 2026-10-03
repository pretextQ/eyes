"""Frozen regression reports, evidence waiting and explicit payload expiration."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0002_platform"
down_revision = "0001_control_plane"
branch_labels = None
depends_on = None


def upgrade():
    for table, column in (
        ("attempts", "evidence_expired_at"),
        ("events", "expired_at"),
        ("evidence_manifests", "expired_at"),
        ("score_runs", "cancel_requested_at"),
    ):
        op.add_column(table, sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.create_table(
        "evidence_waits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempt_id", sa.Uuid(), sa.ForeignKey("attempts.id"), nullable=False),
        sa.Column("scorer_id", sa.Uuid(), sa.ForeignKey("scorer_versions.id"), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.UniqueConstraint("attempt_id", "scorer_id"),
    )
    op.create_index("ix_evidence_waits_attempt_id", "evidence_waits", ["attempt_id"])
    op.create_index("ix_evidence_waits_deadline", "evidence_waits", ["deadline"])
    op.create_table(
        "comparison_reports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("baseline_id", sa.Uuid(), sa.ForeignKey("experiments.id"), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), sa.ForeignKey("experiments.id"), nullable=False),
        sa.Column("request_key", sa.String(200), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.UniqueConstraint("project_id", "request_key"),
    )
    op.create_index("ix_comparison_reports_project_id", "comparison_reports", ["project_id"])
    op.execute(
        "CREATE TRIGGER immutable_record BEFORE UPDATE ON comparison_reports "
        "FOR EACH ROW EXECUTE FUNCTION eyes_reject_version_update()"
    )
    # Retention can only replace payloads with this exact tombstone. Original
    # digests and identifiers remain unchanged; published scores are untouched.
    op.execute("""
        CREATE FUNCTION eyes_expire_payload() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF OLD.expired_at IS NULL AND NEW.expired_at IS NOT NULL
               AND (to_jsonb(NEW) - 'content' - 'expired_at') =
                   (to_jsonb(OLD) - 'content' - 'expired_at') THEN
                IF TG_TABLE_NAME = 'events' AND NEW.content =
                    (OLD.content - 'data') ||
                    jsonb_build_object('data', '{}'::jsonb, 'expired', true) THEN
                    RETURN NEW;
                END IF;
                IF TG_TABLE_NAME = 'evidence_manifests' AND NEW.content =
                    (OLD.content - 'input' - 'expectations' - 'result' - 'evidence_details')
                    || jsonb_build_object('status', 'expired') THEN
                    RETURN NEW;
                END IF;
            END IF;
            RAISE EXCEPTION 'evidence is immutable except for explicit payload expiration';
        END; $$
    """)
    for table in ("events", "evidence_manifests"):
        op.execute(f"DROP TRIGGER immutable_record ON {table}")
        op.execute(
            f"CREATE TRIGGER immutable_record BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION eyes_expire_payload()"
        )


def downgrade():
    for table in ("events", "evidence_manifests"):
        op.execute(f"DROP TRIGGER immutable_record ON {table}")
        op.execute(
            f"CREATE TRIGGER immutable_record BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION eyes_reject_version_update()"
        )
    op.execute("DROP FUNCTION eyes_expire_payload()")
    op.drop_table("comparison_reports")
    op.drop_table("evidence_waits")
    for table, column in (
        ("score_runs", "cancel_requested_at"),
        ("evidence_manifests", "expired_at"),
        ("events", "expired_at"),
        ("attempts", "evidence_expired_at"),
    ):
        op.drop_column(table, column)
