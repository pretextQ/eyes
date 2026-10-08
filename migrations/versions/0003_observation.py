"""Passive Agent telemetry; independent of experiment and Runner state."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003_observation"
down_revision = "0002_platform"
branch_labels = None
depends_on = None


def base_columns():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
    ]


def upgrade():
    op.create_table(
        "observation_sources",
        *base_columns(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("token_digest", sa.String(64), nullable=False, unique=True),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "observed_runs",
        *base_columns(),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("observation_sources.id"), nullable=False),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("session_id", sa.String(200), nullable=False),
        sa.Column("agent", sa.String(200), nullable=False),
        sa.Column("model", sa.String(200), nullable=False),
        sa.Column("capture_body", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("prompt", sa.String(4000)),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminal_sequence", sa.Integer()),
        sa.Column("metrics", JSONB, nullable=False),
        sa.UniqueConstraint("source_id", "external_id"),
    )
    op.create_table(
        "observed_events",
        *base_columns(),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("observation_sources.id"), nullable=False),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("observed_runs.id"), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.UniqueConstraint("run_id", "sequence"),
        sa.UniqueConstraint("source_id", "event_id"),
    )
    for table, columns in (
        ("observation_sources", ["project_id"]),
        ("observed_runs", ["project_id", "source_id", "session_id"]),
        ("observed_events", ["project_id", "run_id"]),
    ):
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])
    op.execute(
        "CREATE TRIGGER immutable_record BEFORE UPDATE ON observed_events "
        "FOR EACH ROW EXECUTE FUNCTION eyes_reject_version_update()"
    )


def downgrade():
    for table in ("observed_events", "observed_runs", "observation_sources"):
        op.drop_table(table)
