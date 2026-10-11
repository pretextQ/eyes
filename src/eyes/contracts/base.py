import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, ValidationInfo, model_validator

SCHEMA_VERSION = "1.0"
LEGACY_SCHEMA_SUNSET = datetime(2026, 11, 1, tzinfo=UTC)
# Only the API boundary activates this explicit, time-limited migration mode.
legacy_request: ContextVar[list[str] | None] = ContextVar("legacy_schema_request", default=None)
logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "password",
    "token",
    "api_key",
    "apikey",
    "api_token",
    "authorization",
    "proxy_authorization",
    "secret",
    "access_token",
    "refresh_token",
    "auth_token",
    "client_secret",
    "private_key",
    "x_api_key",
    "x_auth_token",
    "x_access_token",
    "cookie",
    "set_cookie",
}


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    schema_version: Literal["1.0"]

    @model_validator(mode="before")
    @classmethod
    def explicit_version(cls, value, info: ValidationInfo):
        if isinstance(value, dict) and "schema_version" not in value:
            context = info.context or {}
            audit = context.get("stored_contract_audit")
            if audit is None and datetime.now(UTC) < LEGACY_SCHEMA_SUNSET:
                audit = legacy_request.get()
            if audit is not None:
                audit.append(cls.__name__)
                # Copy, never mutate published snapshots or durable submissions.
                return {"schema_version": SCHEMA_VERSION, **value}
        return value


def read_stored_contract(model, value, *, source):
    """Read pre-strict persisted data in memory; not a public request validator."""
    audit = []
    result = model.model_validate(value, context={"stored_contract_audit": audit})
    if audit:
        logger.warning("legacy_stored_contract source=%s models=%s", source, ",".join(audit))
    return result


def explicit_versions(model, value, *, source):
    """Explicit file migration/outbound projection: preserve every non-version value."""
    parsed = read_stored_contract(model, value, source=source)

    def project(original, validated):
        if isinstance(validated, BaseModel) and isinstance(original, dict):
            result = {
                key: project(child, getattr(validated, key)) for key, child in original.items()
            }
            if isinstance(validated, Contract):
                result["schema_version"] = SCHEMA_VERSION
            return result
        if isinstance(original, list) and isinstance(validated, list):
            return [
                project(child, actual) for child, actual in zip(original, validated, strict=True)
            ]
        if isinstance(original, dict) and isinstance(validated, dict):
            return {key: project(child, validated[key]) for key, child in original.items()}
        return original

    return project(value, parsed)


type Payload = dict[str, JsonValue]
