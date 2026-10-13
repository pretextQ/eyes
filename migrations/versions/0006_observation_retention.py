"""Retain observation identities while expiring content in bounded batches."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0006_observation_retention"
down_revision = "0005_reconciliation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("observed_runs", sa.Column("terminal_received_at", sa.DateTime(timezone=True)))
    op.add_column("observed_runs", sa.Column("expired_at", sa.DateTime(timezone=True)))
    op.add_column(
        "observed_runs",
        sa.Column(
            "expiration_summary", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
    )
    op.add_column("observed_events", sa.Column("expired_at", sa.DateTime(timezone=True)))
    op.execute("DROP TRIGGER immutable_record ON observed_events")
    op.execute("""
        CREATE FUNCTION eyes_expire_observed_event() RETURNS trigger AS $$
        BEGIN
            IF OLD.expired_at IS NULL AND NEW.expired_at IS NOT NULL
               AND NEW.content = '{}'::jsonb
               AND (to_jsonb(NEW) - 'content' - 'expired_at') =
                   (to_jsonb(OLD) - 'content' - 'expired_at')
               AND EXISTS (SELECT 1 FROM observed_runs WHERE id = OLD.run_id
                           AND project_id = OLD.project_id AND expired_at IS NOT NULL)
            THEN RETURN NEW;
            END IF;
            RAISE EXCEPTION 'observed events are immutable except content expiration';
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute(
        "CREATE TRIGGER immutable_record BEFORE UPDATE ON observed_events "
        "FOR EACH ROW EXECUTE FUNCTION eyes_expire_observed_event()"
    )
    # Historical producer timestamps are not a trusted retention clock. Use the
    # last server receipt conservatively; history without a terminal stays protected.
    op.execute(
        "UPDATE observed_runs SET terminal_received_at = GREATEST(created_at, last_seen_at) "
        "WHERE terminal_sequence IS NOT NULL "
        "AND status IN ('completed', 'failed', 'cancelled', 'limited')"
    )
    # Concurrent indexes avoid holding a write-blocking table lock during the build.
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_observed_runs_retention",
            "observed_runs",
            ["project_id", "terminal_received_at", "last_seen_at", "id"],
            postgresql_where=sa.text("expired_at IS NULL AND terminal_received_at IS NOT NULL"),
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_observed_events_retention",
            "observed_events",
            ["project_id", "run_id", "id"],
            postgresql_where=sa.text("expired_at IS NULL"),
            postgresql_concurrently=True,
        )


def downgrade():
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM observed_runs WHERE expired_at IS NOT NULL) "
        "OR EXISTS (SELECT 1 FROM observed_events WHERE expired_at IS NOT NULL) THEN "
        "RAISE EXCEPTION 'expired observation content requires "
        "a pre-expiration backup to downgrade'; "
        "END IF; END $$"
    )
    op.execute("DROP TRIGGER immutable_record ON observed_events")
    op.execute("DROP FUNCTION IF EXISTS eyes_expire_observed_event()")
    op.execute(
        "CREATE TRIGGER immutable_record BEFORE UPDATE ON observed_events "
        "FOR EACH ROW EXECUTE FUNCTION eyes_reject_version_update()"
    )
    op.drop_index("ix_observed_events_retention", table_name="observed_events")
    op.drop_index("ix_observed_runs_retention", table_name="observed_runs")
    op.drop_column("observed_events", "expired_at")
    op.drop_column("observed_runs", "expiration_summary")
    op.drop_column("observed_runs", "expired_at")
    op.drop_column("observed_runs", "terminal_received_at")
