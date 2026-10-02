import hashlib
import mimetypes
import threading
from pathlib import Path
from types import MappingProxyType
from uuid import uuid4

from eyes.runner.files import atomic_write, write_json


class AgentContext:
    def __init__(self, workspace: Path, evidence_dir: Path, recorder, secrets, config, operation):
        self.workspace = workspace.resolve()
        self.evidence_dir = evidence_dir
        self.recorder, self.config = recorder, config
        self.secrets = MappingProxyType(dict(secrets))
        self.cancel_event = threading.Event()
        self.operation = operation
        self.artifact_count = 0
        self.artifact_errors = 0
        self.lock = threading.Lock()

    def span(self, name, attributes=None):
        return self.recorder.span(name, attributes)

    def event(self, kind, data):
        self.recorder.event(kind, data)

    def remote_operation(self, operation_id: str):
        if not operation_id or len(operation_id) > 500:
            raise ValueError("operation identifier must contain 1..500 characters")
        self.operation(operation_id)

    def artifact(self, path: str | Path, *, name=None, media_type=None):
        """Snapshot a workspace file before cleanup. Failures are observation gaps."""
        try:
            with self.lock:
                source = (self.workspace / path).resolve()
                if not source.is_relative_to(self.workspace) or not source.is_file():
                    raise ValueError("artifact must be a regular file inside the workspace")
                if self.artifact_count >= self.config.max_artifacts:
                    raise ValueError("artifact count limit reached")
                with source.open("rb") as stream:
                    data = stream.read(self.config.max_artifact_bytes + 1)
                if len(data) > self.config.max_artifact_bytes:
                    raise ValueError("artifact byte limit reached")
                identifier = str(uuid4())
                directory = self.evidence_dir / "artifacts" / identifier
                atomic_write(directory / "content", data)
                write_json(
                    directory / "metadata.json",
                    {
                        "schema_version": "1.0",
                        "name": name or source.name,
                        "media_type": media_type
                        or mimetypes.guess_type(source.name)[0]
                        or "application/octet-stream",
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                    },
                )
                self.artifact_count += 1
                return identifier
        except Exception:
            self.artifact_errors += 1
            return None


class ScoreContext:
    def __init__(self, workspace: Path, recorder, secrets, artifact_ids):
        self.workspace = workspace
        self.recorder = recorder
        self.secrets = MappingProxyType(dict(secrets))
        self._artifacts = frozenset(artifact_ids)

    def artifact(self, artifact_id: str) -> Path:
        if artifact_id not in self._artifacts:
            raise ValueError("artifact is outside the authorized evidence view")
        return self.workspace / "evidence" / artifact_id

    def span(self, name, attributes=None):
        return self.recorder.span(name, attributes)
