"""Append-only experiment/batch cancellation requests and member handling."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0007_cancellation_audit"
down_revision = "0006_observation_retention"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cancellation_audits",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=False),
        sa.Column("actor_role", sa.String(20), nullable=False),
        sa.Column("object_kind", sa.String(20), nullable=False),
        sa.Column("object_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid()),
        sa.Column("reason", sa.String(1000)),
        sa.Column("key_digest", sa.String(64)),
        sa.Column("request_digest", sa.String(64)),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=False),
        sa.Column("result", JSONB, nullable=False),
        sa.UniqueConstraint("project_id", "actor_id", "key_digest"),
        sa.CheckConstraint("object_kind IN ('experiment', 'batch')", name="ck_cancellation_kind"),
    )
    op.create_index(
        "ix_cancellation_project_time", "cancellation_audits", ["project_id", "created_at", "id"]
    )
    op.create_index(
        "ix_cancellation_object", "cancellation_audits", ["project_id", "object_kind", "object_id"]
    )
    op.create_index("ix_cancellation_audits_parent_id", "cancellation_audits", ["parent_id"])
    op.execute(
        "CREATE TRIGGER immutable_record BEFORE UPDATE OR DELETE ON cancellation_audits "
        "FOR EACH ROW EXECUTE FUNCTION eyes_reject_version_update()"
    )


def downgrade():
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM cancellation_audits) THEN "
        "RAISE EXCEPTION 'cancellation history requires a pre-audit backup to downgrade'; "
        "END IF; END $$"
    )
    op.drop_table("cancellation_audits")
