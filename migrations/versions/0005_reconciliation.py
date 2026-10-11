"""Persist independent unknown-operation query leases and backoff."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0005_reconciliation"
down_revision = "0004_experiment_batches"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "work_items",
        sa.Column("reconciliation", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade():
    op.drop_column("work_items", "reconciliation")
