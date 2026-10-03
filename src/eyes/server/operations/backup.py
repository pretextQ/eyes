"""Consistent database/evidence backups and restore into an empty destination."""

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.engine import make_url

from eyes.server.operations.service import audit, sha256
from eyes.server.scheduling.service import sweep
from eyes.server.storage.database import SCHEMA_REVISION, maintenance_lock
from eyes.server.storage.models import Artifact, Credential, WorkItem, now


def pg_command(settings, program, container=None, bin_dir=None):
    url = make_url(settings.database_url.get_secret_value())
    env = {
        **os.environ,
        "PGUSER": url.username or "",
        "PGPASSWORD": url.password or "",
        "PGDATABASE": url.database or "",
    }
    if container:
        # This must be the container serving EYES_DATABASE_URL, not a sidecar.
        # Credentials are inherited from environment, never command-line values.
        command = [
            "docker",
            "exec",
            "-i",
            "-e",
            "PGUSER",
            "-e",
            "PGPASSWORD",
            "-e",
            "PGDATABASE",
            container,
            program,
            "--host=127.0.0.1",
            "--port=5432",
        ]
    else:
        env.update(PGHOST=url.host or "127.0.0.1", PGPORT=str(url.port or 5432))
        for key, value in url.query.items():
            if key in {"sslmode", "sslrootcert", "sslcert", "sslkey"}:
                env["PG" + key.upper()] = str(value)
        command = [str(bin_dir / program) if bin_dir else program]
    return command, env


def run_pg(settings, program, arguments, *, container=None, bin_dir=None, stdin=None, stdout=None):
    command, env = pg_command(settings, program, container, bin_dir)
    result = subprocess.run(
        command + arguments,
        env=env,
        stdin=stdin,
        stdout=stdout,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        # PostgreSQL diagnostics may include connection credentials or payloads.
        raise RuntimeError(
            f"{program} failed with exit code {result.returncode}; inspect server logs"
        )


def backup(sessions, settings, destination, *, container=None, bin_dir=None):
    destination = destination.resolve()
    root = settings.artifact_root.resolve()
    if destination == root or root in destination.parents:
        raise ValueError("backup directory must be outside the artifact volume")
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    files = destination / "artifacts"
    files.mkdir(mode=0o700)
    dump = destination / "database.dump"
    with sessions() as session, session.begin():
        maintenance_lock(session, exclusive=True)
        revision = session.scalar(text("SELECT version_num FROM alembic_version"))
        if revision != SCHEMA_REVISION:
            raise ValueError("migrate to the current revision before backup")
        inspected = audit(session, root)
        if inspected["status"] != "ok":
            raise ValueError("storage audit failed; refusing an inconsistent backup")
        snapshot = session.scalar(text("SELECT pg_export_snapshot()"))
        with dump.open("xb") as stream:
            run_pg(
                settings,
                "pg_dump",
                ["--format=custom", "--no-owner", "--no-privileges", f"--snapshot={snapshot}"],
                container=container,
                bin_dir=bin_dir,
                stdout=stream,
            )
        with dump.open("rb") as stream:
            os.fsync(stream.fileno())
        inventory = []
        for artifact in session.scalars(select(Artifact).where(Artifact.status == "ready")):
            key = str(UUID(artifact.storage_key))
            source, target = root / key, files / key
            shutil.copyfile(source, target)
            target.chmod(0o600)
            with target.open("rb") as stream:
                os.fsync(stream.fileno())
            inventory.append({"key": key, "size": target.stat().st_size, "sha256": sha256(target)})
        manifest = {
            "schema_version": "1.0",
            "database_revision": revision,
            "created_at": now().isoformat(),
            "database_sha256": sha256(dump),
            "artifacts": inventory,
            "audit": inspected,
            "pending_uploads": "metadata only; unfinished bytes are not backed up",
        }
        # A manifest is the completion marker. A failed backup never has one.
        path = destination / "manifest.json"
        with path.open("x") as stream:
            json.dump(manifest, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        for folder in (files, destination):
            fd = os.open(folder, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
    dump.chmod(0o600)
    return {
        "status": "complete",
        "directory": str(destination),
        "artifacts": len(inventory),
        "database_revision": revision,
    }


def restore(sessions, settings, source, *, container=None, bin_dir=None):
    source = source.resolve()
    manifest = json.loads((source / "manifest.json").read_text())
    if manifest.get("schema_version") != "1.0" or manifest["database_revision"] != SCHEMA_REVISION:
        raise ValueError("backup protocol or database revision does not match this service")
    dump = source / "database.dump"
    if dump.is_symlink() or sha256(dump) != manifest["database_sha256"]:
        raise ValueError("backup database digest does not match")
    root = settings.artifact_root.resolve()
    if root == source or source in root.parents or root in source.parents:
        raise ValueError("restore volume must be separate from backup directory")
    if root.exists() and any(root.iterdir()):
        raise ValueError("restore artifact directory must be empty")
    inventory = manifest["artifacts"]
    seen = set()
    for item in inventory:
        key = str(UUID(item["key"]))
        if key != item["key"] or key in seen:
            raise ValueError("invalid or duplicated artifact key")
        seen.add(key)
        path = source / "artifacts" / key
        if (
            path.is_symlink()
            or path.stat().st_size != item["size"]
            or sha256(path) != item["sha256"]
        ):
            raise ValueError("backup artifact integrity failure")
    root.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".eyes-restore-", dir=root.parent))
    try:
        for item in inventory:
            shutil.copyfile(source / "artifacts" / item["key"], staging / item["key"])
            (staging / item["key"]).chmod(0o600)
        with sessions() as session, session.begin():
            maintenance_lock(session, exclusive=True)
            tables = session.scalar(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema NOT IN ('pg_catalog','information_schema')"
                )
            )
            if tables:
                raise ValueError(
                    "restore requires an empty database; existing data is never overwritten"
                )
            # pg_restore uses a separate connection and a single transaction.
            with dump.open("rb") as stream:
                run_pg(
                    settings,
                    "pg_restore",
                    [
                        "--dbname="
                        + (make_url(settings.database_url.get_secret_value()).database or ""),
                        "--single-transaction",
                        "--exit-on-error",
                        "--no-owner",
                        "--no-privileges",
                    ],
                    container=container,
                    bin_dir=bin_dir,
                    stdin=stream,
                    stdout=subprocess.DEVNULL,
                )
            if root.exists():
                root.rmdir()
            os.replace(staging, root)
            inspected = audit(session, root)
            if inspected["status"] != "ok":
                raise ValueError("restored storage audit failed; keep services stopped")
            # Restored leases must not authenticate old Runner processes. Preserve
            # unknown execution reservations; require operators to reconcile them.
            for credential in session.scalars(
                select(Credential).where(Credential.role == "runner")
            ):
                credential.revoked = True
            for work in session.scalars(select(WorkItem).where(WorkItem.status == "claimed")):
                work.lease_expires_at = now()
            recovery = sweep(session, settings)
        return {
            "status": "complete",
            "audit": inspected,
            "recovery": recovery,
            "runner_credentials": "revoked; reconcile unknown executions, then issue new tokens",
        }
    finally:
        if staging.exists():
            shutil.rmtree(staging)
