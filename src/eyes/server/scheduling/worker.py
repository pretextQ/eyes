import argparse
import json
import logging
import signal
import threading

from sqlalchemy.exc import SQLAlchemyError

from eyes.server.config import Settings
from eyes.server.scheduling.service import sweep
from eyes.server.storage.database import database


def main():
    parser = argparse.ArgumentParser(description="Eyes PostgreSQL scheduling coordinator")
    parser.add_argument("--once", action="store_true", help="run one sweep and exit")
    args = parser.parse_args()
    settings = Settings()
    engine, sessions = database(settings)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        while not stop.is_set():
            try:
                with sessions() as session, session.begin():
                    result = sweep(session, settings)
                logging.info("scheduling_sweep %s", json.dumps(result))
            except SQLAlchemyError:
                logging.error("scheduling_sweep failed; no acknowledgement committed")
                if args.once:
                    raise SystemExit(2) from None
            if args.once:
                break
            stop.wait(settings.scheduler_interval_seconds)
    finally:
        engine.dispose()
