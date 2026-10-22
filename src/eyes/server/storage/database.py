from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from eyes.server.config import Settings


def schema_revision():
    source = Path(__file__).resolve().parents[4] / "migrations"
    bundled = Path(__file__).with_name("migrations")
    directory = source if (source / "versions").is_dir() else bundled
    revision = ScriptDirectory(str(directory)).get_current_head()
    if revision is None:
        raise RuntimeError("service requires a single packaged Alembic head")
    return revision


SCHEMA_REVISION = schema_revision()


def database(settings: Settings):
    engine = create_engine(
        settings.database_url.get_secret_value(), pool_pre_ping=True, hide_parameters=True
    )
    return engine, sessionmaker(engine, expire_on_commit=False)


def scheduling_lock(session: Session) -> None:
    # Fixed order across claim, finish, cancellation and recovery. Global reservations
    # are counted only while these locks are held; keep all network I/O outside them.
    session.execute(text("SELECT pg_advisory_xact_lock(74001)"))
    session.execute(text("SELECT pg_advisory_xact_lock(74002)"))


def maintenance_lock(session: Session, *, exclusive=False) -> None:
    # Always acquire before scheduling/row locks. Backup and retention use the
    # exclusive form; normal control-plane transactions take a shared lock.
    suffix = "" if exclusive else "_shared"
    session.execute(text(f"SELECT pg_advisory_xact_lock{suffix}(74000)"))
