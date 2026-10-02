import argparse
import hashlib
import json
import secrets
from uuid import UUID

from sqlalchemy import select

from eyes.server.config import Settings
from eyes.server.storage.database import database
from eyes.server.storage.models import Credential, Project, TargetVersion


def issue(session, project_id, role, targets, kinds):
    token = "eyes_" + secrets.token_urlsafe(32)
    credential = Credential(
        project_id=project_id,
        role=role,
        token_digest=hashlib.sha256(token.encode()).hexdigest(),
        target_ids=[str(tid) for tid in targets],
        work_kinds=kinds,
    )
    session.add(credential)
    session.flush()
    return {
        "credential_id": str(credential.id),
        "project_id": str(project_id),
        "role": role,
        "token": token,
    }


def main():
    parser = argparse.ArgumentParser(description="Local Eyes project and credential administration")
    commands = parser.add_subparsers(dest="command", required=True)
    bootstrap = commands.add_parser("bootstrap")
    bootstrap.add_argument("--name", required=True)
    bootstrap.add_argument("--execution-limit", type=int, default=8)
    bootstrap.add_argument("--score-limit", type=int, default=2)
    token = commands.add_parser("issue-token")
    token.add_argument("--project-id", type=UUID, required=True)
    token.add_argument("--role", choices=["read", "manage", "runner"], required=True)
    token.add_argument("--target-id", type=UUID, action="append", default=[])
    token.add_argument("--all-targets", action="store_true")
    token.add_argument("--work-kind", choices=["execute", "score"], action="append", default=[])
    revoke = commands.add_parser("revoke-token")
    revoke.add_argument("--credential-id", type=UUID, required=True)
    args = parser.parse_args()
    engine, sessions = database(Settings())
    try:
        with sessions() as session, session.begin():
            if args.command == "bootstrap":
                if args.execution_limit < 1 or args.score_limit < 1:
                    parser.error("capacity limits must be positive")
                project = Project(
                    name=args.name,
                    execution_limit=args.execution_limit,
                    score_limit=args.score_limit,
                )
                session.add(project)
                session.flush()
                result = issue(session, project.id, "manage", [], [])
            elif args.command == "issue-token":
                if session.get(Project, args.project_id) is None:
                    parser.error("project not found")
                if args.role == "runner":
                    if not args.work_kind or (not args.target_id and not args.all_targets):
                        parser.error("Runner needs --work-kind and --target-id or --all-targets")
                    if args.all_targets and args.target_id:
                        parser.error("choose --all-targets or --target-id")
                elif args.target_id or args.all_targets or args.work_kind:
                    parser.error("target and work-kind scopes apply to Runner tokens only")
                for target_id in args.target_id:
                    if (
                        session.scalar(
                            select(TargetVersion).where(
                                TargetVersion.id == target_id,
                                TargetVersion.project_id == args.project_id,
                            )
                        )
                        is None
                    ):
                        parser.error("target not found in project")
                result = issue(session, args.project_id, args.role, args.target_id, args.work_kind)
            else:
                credential = session.get(Credential, args.credential_id)
                if credential is None:
                    parser.error("credential not found")
                credential.revoked = True
                result = {"credential_id": str(credential.id), "revoked": True}
        # Tokens print only after commit succeeds, exactly once at issuance.
        print(json.dumps(result))
    finally:
        engine.dispose()
