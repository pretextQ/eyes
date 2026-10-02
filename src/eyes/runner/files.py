import hashlib
import json
import os
import tempfile
from pathlib import Path

from eyes.contracts.base import SENSITIVE_KEYS, Payload


def json_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def atomic_write(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".writing-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_json(path: Path, value):
    atomic_write(path, json_bytes(value))


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def redact(value, secrets=()):
    if isinstance(value, dict):
        return {
            key: "[redacted]"
            if key.lower().replace("-", "_") in SENSITIVE_KEYS
            else redact(child, secrets)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact(item, secrets) for item in value]
    if isinstance(value, str):
        for secret in sorted(set(secrets), key=len, reverse=True):
            if secret:
                value = value.replace(secret, "[redacted]")
    return value


def error_text(error: BaseException, secrets=(), limit=1800) -> str:
    return str(redact(f"{type(error).__name__}: {error}", secrets))[:limit]


def resolve_secrets(refs: dict[str, str], allowed: list[str], token_env: str) -> Payload:
    resolved = {}
    for name, reference in refs.items():
        if not reference.startswith("env:"):
            raise ValueError("secret references must have env:NAME form")
        variable = reference[4:]
        if variable == token_env or variable not in allowed:
            raise ValueError(f"secret environment variable is not authorized: {variable}")
        if variable not in os.environ:
            raise ValueError(f"secret environment variable is missing: {variable}")
        resolved[name] = os.environ[variable]
    return resolved
