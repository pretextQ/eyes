from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from eyes.server.config import Settings


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
