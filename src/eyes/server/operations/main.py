import argparse
import json
import signal
import sys
from pathlib import Path
from threading import Event
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from eyes.server.config import Settings
from eyes.server.domain import DomainError
from eyes.server.observation.retention import maintain_observations
from eyes.server.operations import service
from eyes.server.storage.database import database, maintenance_lock


def main():
    parser = argparse.ArgumentParser(
        description="Eyes storage audit, retention, backup and empty-destination restore"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("audit")
    capacity_command = commands.add_parser("capacity", help="current capacity and keyed alerts")
    capacity_command.add_argument("--project-id", required=True, type=UUID)
    maintain = commands.add_parser(
        "maintain", help="preview by default; --apply commits retention and reclaims files"
    )
    maintain.add_argument("--apply", action="store_true")
    maintain.add_argument("--project-id", type=UUID, help="observation retention project scope")
    maintain.add_argument(
        "--observations-only", action="store_true", help="skip experimental artifact maintenance"
    )
    maintain.add_argument(
        "--interval", type=float, default=0, help="repeat maintenance every N seconds; 0 runs once"
    )
    maintain.add_argument(
        "--attempt-id",
        type=UUID,
        help="explicitly expire one inactive attempt regardless of retention age",
    )
    for name in ("backup", "restore"):
        command = commands.add_parser(name)
        command.add_argument("directory", type=Path)
        group = command.add_mutually_exclusive_group()
        group.add_argument(
            "--pg-container",
            help="PostgreSQL container serving EYES_DATABASE_URL (internal port 5432)",
        )
        group.add_argument(
            "--pg-bin-dir", type=Path, help="directory containing pg_dump/pg_restore"
        )
    args = parser.parse_args()
    settings = Settings()
    engine, sessions = database(settings)
    try:
        if args.command in {"backup", "restore"}:
            from eyes.server.operations.backup import backup, restore

            action = backup if args.command == "backup" else restore
            result = action(
                sessions,
                settings,
                args.directory,
                container=args.pg_container,
                bin_dir=args.pg_bin_dir,
            )
        elif args.command == "capacity":
            from eyes.server.operations.capacity import status
            from eyes.server.storage.models import Project

            with sessions() as session, session.begin():
                maintenance_lock(session)
                if session.get(Project, args.project_id) is None:
                    raise ValueError("project does not exist")
                result = status(session, settings, args.project_id)
        elif args.command == "audit":
            with sessions() as session, session.begin():
                maintenance_lock(session, exclusive=True)
                result = service.audit(session, settings.artifact_root)
        else:
            if args.interval < 0 or (args.interval and args.attempt_id):
                raise ValueError("interval must be nonnegative; explicit expiration runs once")
            stopping = Event()
            if args.interval:
                # Complete the current bounded round, then stop without waiting
                # through the interval or requiring Docker to kill PID 1.
                def stop(_signum, _frame):
                    stopping.set()

                signal.signal(signal.SIGTERM, stop)
                signal.signal(signal.SIGINT, stop)
            while True:
                if args.observations_only and args.attempt_id:
                    raise ValueError("--observations-only cannot be combined with --attempt-id")
                observations = (
                    maintain_observations(
                        sessions, settings, apply=args.apply, project_id=args.project_id
                    )
                    if not args.attempt_id
                    else None
                )
                result = {"schema_version": "1.0", "mode": "apply" if args.apply else "preview"}
                if not args.observations_only:
                    with sessions() as session, session.begin():
                        result, _ = service.maintain(
                            session, settings, apply=args.apply, attempt_id=args.attempt_id
                        )
                result["observations"] = observations
                if args.apply and not args.observations_only:
                    with sessions() as session, session.begin():
                        _, paths = service.maintain(session, settings)
                        result["delete_failures"] = service.reclaim(paths)
                        result["deleted_files"] = len(paths) - len(result["delete_failures"])
                if not args.interval:
                    break
                print(json.dumps(result, ensure_ascii=False), flush=True)
                if stopping.wait(args.interval):
                    break
        print(json.dumps(result, ensure_ascii=False))
        if result.get("status") == "error" or result.get("delete_failures"):
            raise SystemExit(1)
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        RuntimeError,
        DomainError,
        SQLAlchemyError,
    ) as error:
        print(
            json.dumps(
                {
                    "error": "operation_failed",
                    "type": type(error).__name__,
                    "code": error.code if isinstance(error, DomainError) else None,
                    "message": str(error)
                    if isinstance(error, (ValueError, RuntimeError))
                    else error.message
                    if isinstance(error, DomainError)
                    else "check database connectivity, permissions and server logs",
                }
            ),
            file=sys.stderr,
        )
        raise SystemExit(3) from None
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
