"""Index work_items by experiment and attempt so scheduling reads stop scanning."""

from alembic import op

revision = "0008_work_indexes"
down_revision = "0007_cancellation_audit"
branch_labels = None
depends_on = None


def upgrade():
    # refresh_experiment runs on every work completion and reads only the statuses
    # of one experiment. Including status makes that read index-only.
    op.create_index("ix_work_items_experiment", "work_items", ["experiment_id", "status"])
    # Evidence download and score lookup resolve a single work item by attempt.
    op.create_index("ix_work_items_attempt", "work_items", ["attempt_id"])


def downgrade():
    op.drop_index("ix_work_items_attempt", table_name="work_items")
    op.drop_index("ix_work_items_experiment", table_name="work_items")
