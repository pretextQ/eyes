import os
import socket
import sys
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from eyes.contracts.target import http_origin as origin


class Binding(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entry_point: str = Field(pattern=r"^[A-Za-z_][\w.]*:[A-Za-z_][\w.]*$")
    python: str = sys.executable
    import_paths: list[Path] = Field(default_factory=list)
    prepare: str | None = None
    cleanup: str | None = None
    cancel: str | None = None
    reconcile: str | None = None
    execution_scope: Literal["process", "external"] = "external"
    session_isolation: bool = True
    environment_isolation: bool = False
    idempotency: bool = False
    implementation_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    cpu_seconds: int | None = Field(default=None, ge=1)
    memory_bytes: int | None = Field(default=None, ge=64 * 1024 * 1024)
    file_bytes: int = Field(default=64 * 1024 * 1024, ge=1024)


class RunnerConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    server_url: str = "http://127.0.0.1:8000"
    token_env: str = "EYES_RUNNER_TOKEN"
    name: str = Field(default_factory=socket.gethostname)
    state_dir: Path = Path("data/runner")
    execution_slots: int = Field(default=1, ge=0, le=100)
    score_slots: int = Field(default=1, ge=0, le=100)
    poll_seconds: float = Field(default=2, ge=0.1)
    api_timeout_seconds: float = Field(default=5, ge=0.1, le=60)
    stop_grace_seconds: float = Field(default=5, ge=0.1, le=60)
    cleanup_timeout_seconds: float = Field(default=10, ge=0.1, le=120)
    evidence_wait_seconds: float = Field(default=10, ge=0, le=120)
    max_message_bytes: int = Field(default=1024 * 1024, ge=4096)
    max_score_input_bytes: int = Field(default=32 * 1024 * 1024, ge=4096, le=128 * 1024 * 1024)
    max_event_bytes: int = Field(default=64 * 1024, ge=1024)
    event_queue_size: int = Field(default=256, ge=1, le=10000)
    event_disk_bytes: int = Field(default=8 * 1024 * 1024, ge=65536)
    outbox_bytes: int = Field(default=128 * 1024 * 1024, ge=1024 * 1024)
    max_artifact_bytes: int = Field(default=32 * 1024 * 1024, ge=1024)
    max_artifacts: int = Field(default=20, ge=0, le=1000)
    allowed_http_origins: list[str] = Field(default_factory=list)
    secret_env_allowlist: list[str] = Field(default_factory=list)
    python_agents: dict[str, Binding] = Field(default_factory=dict)
    python_scorers: dict[str, Binding] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_config(self):
        origin(self.server_url)
        self.allowed_http_origins = [origin(item) for item in self.allowed_http_origins]
        if not self.execution_slots and not self.score_slots:
            raise ValueError("at least one execution or score slot is required")
        if self.token_env in self.secret_env_allowlist:
            raise ValueError("platform Runner token must not be exposed to plugins")
        if self.max_message_bytes > 8 * 1024 * 1024:
            raise ValueError("max_message_bytes cannot exceed the control API JSON limit")
        if not self.name or len(self.name) > 200:
            raise ValueError("Runner name must contain 1..200 characters")
        if "rules" in self.python_scorers:
            raise ValueError("rules is reserved for the built-in scorer")
        if os.name != "posix":
            raise ValueError("this Runner requires POSIX process groups (macOS or Linux)")
        return self


def load_config(path: Path) -> RunnerConfig:
    config = RunnerConfig.model_validate(tomllib.loads(path.read_text()))
    base = path.resolve().parent
    if not config.state_dir.is_absolute():
        config.state_dir = (base / config.state_dir).resolve()
    for binding in [*config.python_agents.values(), *config.python_scorers.values()]:
        binding.import_paths = [(base / item).resolve() for item in binding.import_paths]
        if "/" in binding.python and not Path(binding.python).is_absolute():
            binding.python = str((base / binding.python).resolve())
    return config
