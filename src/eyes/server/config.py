from pathlib import Path
from uuid import UUID

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EYES_", env_file=".env", extra="ignore")

    database_url: SecretStr = SecretStr("postgresql+psycopg://eyes:eyes@127.0.0.1:5432/eyes")
    artifact_root: Path = Path("data/artifacts")
    max_request_bytes: int = Field(default=8 * 1024 * 1024, ge=1024)
    max_score_input_bytes: int = Field(default=32 * 1024 * 1024, ge=4096, le=128 * 1024 * 1024)
    max_artifact_bytes: int = Field(default=32 * 1024 * 1024, ge=1024)
    max_dataset_cases: int = Field(default=10000, ge=1)
    max_experiment_runs: int = Field(default=100000, ge=1)
    max_preparation_attempts: int = Field(default=3, ge=1, le=100)
    global_execution_limit: int = Field(default=16, ge=1)
    global_score_limit: int = Field(default=4, ge=1)
    lease_seconds: int = Field(default=60, ge=5, le=3600)
    cancellation_grace_seconds: int = Field(default=60, ge=1)
    score_submission_grace_seconds: int = Field(default=60, ge=1, le=3600)
    scheduler_interval_seconds: float = Field(default=5, ge=0.1)
    evidence_retention_days: int = Field(default=0, ge=0)
    pending_artifact_ttl_hours: int = Field(default=24, ge=1)
    orphan_artifact_grace_hours: int = Field(default=24, ge=1)
    trace_console_export: bool = False
    local_observation: bool = False
    local_observation_project_id: UUID | None = None

    @field_validator("database_url")
    @classmethod
    def postgres_only(cls, value):
        if make_url(value.get_secret_value()).drivername != "postgresql+psycopg":
            raise ValueError("EYES_DATABASE_URL must use postgresql+psycopg")
        return value
