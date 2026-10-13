"""Measured admission limits and current, keyed alerts; no reservation ledger."""

import shutil
from datetime import UTC, datetime

from sqlalchemy import text

from eyes.server.domain import DomainError

USAGE_SQL = """
SELECT project_id, sum(bytes)::bigint AS bytes FROM (
    SELECT project_id, octet_length(content::text) AS bytes FROM events
    UNION ALL
    SELECT project_id, octet_length(content::text) AS bytes FROM observed_events
) contents GROUP BY project_id
"""


def event_usage(connection):
    return {str(row.project_id): row.bytes for row in connection.execute(text(USAGE_SQL))}


def begin_admission(session, transaction, connection, settings):
    # API transactions acquire this BEFORE any producer, attempt or scheduling
    # lock. All workers must run the same configuration. READ COMMITTED sees the
    # previous holder's commit before recording the baseline.
    if settings.project_event_content_bytes:
        connection.exec_driver_sql("SELECT pg_advisory_xact_lock(74003)")
        session.info["capacity_baseline"] = event_usage(connection)


def finish_admission(session, settings):
    baseline = session.info.get("capacity_baseline")
    if baseline is None:
        return
    session.flush()
    current = event_usage(session.connection())
    for project, used in current.items():
        previous = baseline.get(project, 0)
        # Already over limit after enabling: allow duplicates and reductions.
        if used > previous and used > settings.project_event_content_bytes:
            raise DomainError(
                507,
                "project_event_capacity_exceeded",
                "project retained event content quota would be exceeded",
                {
                    "scope": "project_event_content",
                    "project_id": project,
                    "used_bytes": previous,
                    "requested_growth_bytes": used - previous,
                    "limit_bytes": settings.project_event_content_bytes,
                    "measured_at": datetime.now(UTC).isoformat(),
                    "retryable": True,
                },
            )


def volume_status(root, minimum):
    measured = datetime.now(UTC).isoformat()
    try:
        usage = shutil.disk_usage(root)
        return {
            "scope": "artifact_volume",
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "total_bytes": usage.total,
            "minimum_free_bytes": minimum,
            "measured_at": measured,
            "state": "blocked" if minimum and usage.free < minimum else "ok",
            "reason": "below_minimum_free_bytes" if minimum and usage.free < minimum else None,
        }
    except OSError as error:
        return {
            "scope": "artifact_volume",
            "used_bytes": None,
            "free_bytes": None,
            "total_bytes": None,
            "minimum_free_bytes": minimum,
            "measured_at": measured,
            "state": "unknown",
            "reason": f"volume_measurement_failed:{error.errno}",
        }


def status(session, settings, project_id):
    used = event_usage(session.connection()).get(str(project_id), 0)
    limit = settings.project_event_content_bytes
    content = {
        "scope": "project_event_content",
        "project_id": str(project_id),
        "used_bytes": used,
        "limit_bytes": limit,
        "warning_percent": settings.capacity_warning_percent,
        "measured_at": datetime.now(UTC).isoformat(),
        "state": "blocked"
        if limit and used >= limit
        else "warning"
        if limit and used * 100 >= limit * settings.capacity_warning_percent
        else "ok",
        "reason": "quota_reached"
        if limit and used >= limit
        else "quota_near_limit"
        if limit and used * 100 >= limit * settings.capacity_warning_percent
        else None,
    }
    volume = volume_status(settings.artifact_root, settings.artifact_min_free_bytes)
    # A current-state alert set, keyed by scope/project, replaces append-only
    # poll records. Recovery removes the key on the next measurement.
    alerts = [
        {"id": f"capacity:{item['scope']}:{project_id}", **item}
        for item in (content, volume)
        if item["state"] != "ok"
    ]
    return {"schema_version": "1.0", "measurements": [content, volume], "alerts": alerts}
