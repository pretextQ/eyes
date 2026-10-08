"""Group independently configured Agent experiments into an atomic batch."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004_experiment_batches"
down_revision = "0003_observation"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "experiment_batches",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("project_id", sa.Uuid(), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("request_key", sa.String(200), nullable=False),
        sa.Column("request_digest", sa.String(64), nullable=False),
        sa.Column("snapshot", JSONB, nullable=False),
        sa.UniqueConstraint("project_id", "request_key"),
    )
    op.create_index("ix_experiment_batches_project_id", "experiment_batches", ["project_id"])
    op.add_column("experiments", sa.Column("batch_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_experiments_batch_id", "experiments", "experiment_batches", ["batch_id"], ["id"]
    )
    op.create_index("ix_experiments_batch_id", "experiments", ["batch_id"])


def downgrade():
    op.drop_index("ix_experiments_batch_id", table_name="experiments")
    op.drop_constraint("fk_experiments_batch_id", "experiments", type_="foreignkey")
    op.drop_column("experiments", "batch_id")
    op.drop_table("experiment_batches")
