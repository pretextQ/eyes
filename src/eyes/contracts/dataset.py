from pydantic import Field, model_validator

from eyes.contracts.base import Contract, Payload


class CaseDefinition(Contract):
    case_id: str = Field(min_length=1, max_length=200)
    input: Payload
    expectations: Payload = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list, max_length=100)
    environment: Payload = Field(default_factory=dict)
    artifact_requirements: list[str] = Field(default_factory=list, max_length=100)
    preparation_version: str | None = None
    environment_limitations: list[str] = Field(default_factory=list)
    steps: list[Payload] = Field(default_factory=list)

    @model_validator(mode="after")
    def single_turn_only(self):
        if self.steps:
            raise ValueError("multi-turn steps are not supported by this backend version")
        return self


class DatasetImport(Contract):
    name: str = Field(min_length=1, max_length=200)
    jsonl: str = Field(min_length=1)
