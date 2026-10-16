"""Offline API/real PostgreSQL checks with synthetic identities; no Agent or model."""

import asyncio
import copy
import hashlib
import json
import os
import secrets
import sys
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import httpx
from sqlalchemy import func, select

from eyes.server.api.app import create_app
from eyes.server.config import Settings
from eyes.server.storage.database import database
from eyes.server.storage.models import (
    Attempt,
    Base,
    CaseRun,
    CaseVersion,
    Credential,
    DatasetVersion,
    Experiment,
    Project,
    ResolutionRecord,
    Runner,
    ScoreRun,
    Target,
    TargetVersion,
    WorkItem,
    now,
)

STATE = Path("/verify/state.json")


def seed(settings):
    engine, sessions = database(settings)
    # This driver is only allowed to initialize a fresh, dedicated database.
    assert not engine.dialect.has_table(engine.connect(), "attempts"), "database is not empty"
    Base.metadata.create_all(engine)
    with sessions.begin() as session:
        project = Project(name="offline-reconciliation")
        other = Project(name="other-project")
        session.add_all([project, other])
        session.flush()
        tokens = {}
        credentials = {}
        for name, role, scope in (
            ("manager", "manage", project),
            ("reader", "read", project),
            ("runner", "runner", project),
            ("foreign", "manage", other),
        ):
            token = secrets.token_hex(32)
            tokens[name] = token
            credential = Credential(
                project_id=scope.id,
                role=role,
                token_digest=hashlib.sha256(token.encode()).hexdigest(),
            )
            session.add(credential)
            credentials[name] = credential
        session.flush()
        runner = Runner(credential_id=credentials["runner"].id, name="offline", capabilities={})
        target = Target(project_id=project.id, name="offline", concurrency_limit=1)
        dataset = DatasetVersion(project_id=project.id, name="offline", digest="0" * 64, content={})
        session.add_all([runner, target, dataset])
        session.flush()
        version = TargetVersion(
            project_id=project.id, target_id=target.id, name="offline", digest="0" * 64, content={}
        )
        case = CaseVersion(
            dataset_id=dataset.id,
            case_id="offline",
            digest="0" * 64,
            content={"input": {}, "expectations": {}},
        )
        session.add_all([version, case])
        session.flush()
        experiment = Experiment(
            project_id=project.id,
            target_id=version.id,
            target_scope_id=target.id,
            dataset_id=dataset.id,
            request_key="offline",
            request_digest="0" * 64,
            snapshot={},
            status="completed_with_unresolved",
        )
        session.add(experiment)
        session.flush()
        run = CaseRun(
            experiment_id=experiment.id, case_version_id=case.id, repetition=0, status="unknown"
        )
        session.add(run)
        session.flush()
        attempt = Attempt(
            project_id=project.id,
            case_run_id=run.id,
            runner_id=runner.id,
            trace_id="1" * 32,
            root_span_id="2" * 16,
            idempotency_key=secrets.token_hex(24),
            deadline=now() + timedelta(seconds=30),
            execution_intent_at=now(),
            status="unknown",
            remote_operation_id=str(uuid4()),
            cleanup_status="unknown",
            evidence_status="partial",
            result={"status": "unknown", "error": "offline HTTP error"},
        )
        session.add(attempt)
        session.flush()
        work = WorkItem(
            project_id=project.id,
            experiment_id=experiment.id,
            target_id=version.id,
            target_scope_id=target.id,
            case_run_id=run.id,
            attempt_id=attempt.id,
            kind="execute",
            plugin="agent_http",
            status="unknown",
            reserved=True,
        )
        session.add(work)
        session.flush()
        body = {
            "schema_version": "1.0",
            "evidence_id": str(uuid4()),
            "expected_attempt_id": str(attempt.id),
            "expected_task_id": str(run.id),
            "expected_run_id": attempt.remote_operation_id,
            "idempotency_key_sha256": hashlib.sha256(attempt.idempotency_key.encode()).hexdigest(),
            "source": "supplier_record",
            "source_reference": str(uuid4()),
            "evidence_sha256": hashlib.sha256(b"synthetic offline evidence").hexdigest(),
            "observed_at": now().isoformat(),
            "reason": "offline supplier evidence",
        }
        state = {"tokens": tokens, "attempt": str(attempt.id), "work": str(work.id), "body": body}
    STATE.write_text(json.dumps(state))
    STATE.chmod(0o600)
    engine.dispose()
    return state


def inspect(app, state, status, reserved):
    with app.state.sessions() as session:
        from uuid import UUID

        attempt = session.get(Attempt, UUID(state["attempt"]))
        work = session.get(WorkItem, UUID(state["work"]))
        assert (attempt.status, work.reserved, attempt.cleanup_status) == (
            status,
            reserved,
            "unknown",
        )
        assert session.scalar(select(func.count()).select_from(ScoreRun)) == 0
        return session.scalar(select(func.count()).select_from(ResolutionRecord))


async def main():
    settings = Settings(
        _env_file=None,
        database_url=os.environ["VERIFY_DATABASE_URL"],
        artifact_root="/verify/artifacts",
    )
    assert "/eyes_unknown_verify" in settings.database_url.get_secret_value()
    restart = len(sys.argv) > 1 and sys.argv[1] == "restart"
    state = json.loads(STATE.read_text()) if restart else seed(settings)
    app = create_app(settings)
    path = f"/v1/attempts/{state['attempt']}/reconciliation-evidence"
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://offline"
        ) as client,
    ):

        async def send(body, expected=200, role="manager"):
            headers = {"Authorization": "Bearer " + state["tokens"][role]} if role else {}
            response = await client.post(path, json=body, headers=headers)
            assert response.status_code == expected, (response.status_code, response.text)
            return response.json()

        if restart:
            count = inspect(app, state, "failed", False)
            assert await send(state["applied_body"]) == state["receipt"]
            assert inspect(app, state, "failed", False) == count
            changed = {**state["applied_body"], "billing": "charged"}
            await send(changed, 409)
            print(json.dumps({"scenario": "fresh-process-after-database-restart", "passed": True}))
            return
        base = state["body"]
        for role, code in ((None, 401), ("reader", 403), ("runner", 403), ("foreign", 404)):
            await send(base, code, role)
        for key in ("expected_attempt_id", "expected_task_id", "expected_run_id"):
            await send({**base, key: str(uuid4())}, 409)
        await send({**base, "idempotency_key_sha256": "0" * 64}, 409)
        await send({**base, "source": "http500"}, 422)
        await send({**base, "source_reference": "https://secret.invalid/?token=x"}, 422)
        for body in (
            {**base, "apply": True},
            {**base, "apply": True, "status": "failed"},
            {**base, "apply": True, "stopped_confirmed": True},
        ):
            await send(body, 422)
        assert inspect(app, state, "unknown", True) == 0
        observed = await send(base)
        assert not observed["applied"] and not observed["billing_settled"]
        count = inspect(app, state, "unknown", True)
        assert await send(base) == observed
        assert inspect(app, state, "unknown", True) == count
        await send({**base, "reason": "conflict"}, 409)
        stop = {**base, "evidence_id": str(uuid4()), "stopped_confirmed": True}
        await send(stop)
        inspect(app, state, "unknown", True)
        bill = {**base, "evidence_id": str(uuid4()), "billing": "not_charged"}
        await send(bill)
        inspect(app, state, "unknown", True)
        await send({**bill, "evidence_id": str(uuid4()), "billing": "charged"}, 409)
        apply = {
            **stop,
            "evidence_id": str(uuid4()),
            "status": "failed",
            "apply": True,
        }
        receipt = await send(apply)
        assert receipt["applied"] and not receipt["billing_settled"]
        count = inspect(app, state, "failed", False)
        assert await send(apply) == receipt
        assert inspect(app, state, "failed", False) == count
        await send({**apply, "evidence_id": str(uuid4()), "status": "timed_out"}, 409)
        with app.state.sessions() as session:
            records = session.scalars(select(ResolutionRecord)).all()
            audit = next(r.content for r in records if r.content.get("receipt", {}).get("applied"))
            assert audit["before"]["status"] == "unknown" and audit["before"]["reserved"]
            assert audit["after"]["status"] == "failed" and not audit["after"]["reserved"]
            assert audit["after"]["result"]["previous_result"] == audit["before"]["result"]
        state.update(applied_body=copy.deepcopy(apply), receipt=receipt)
        STATE.write_text(json.dumps(state))
        print(json.dumps({"scenario": "manual-evidence-api", "passed": True}), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
