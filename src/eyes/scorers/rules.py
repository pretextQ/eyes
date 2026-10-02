from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from eyes.adapters.http import pointer
from eyes.contracts.base import Payload
from eyes.contracts.scorer import ScoreOutput
from eyes.runner.files import json_bytes


class Check(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["equals", "contains", "event", "artifact"] = "equals"
    pointer: str = Field(default="", pattern=r"^(|/.*)$")
    value: object = None
    expectation_pointer: str | None = Field(default=None, pattern=r"^(|/.*)$")
    type: str | None = Field(default=None, min_length=1)
    data: Payload = Field(default_factory=dict)
    name: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def required_fields(self):
        if self.kind in {"equals", "contains"}:
            if ("value" in self.model_fields_set) == (self.expectation_pointer is not None):
                raise ValueError("comparison needs exactly one value or expectation_pointer")
        if self.kind == "event" and self.type is None:
            raise ValueError("event check needs type")
        if self.kind == "artifact" and self.name is None:
            raise ValueError("artifact check needs name")
        return self


def score(request, context):
    rules = request.scorer.config.get("checks")
    if not isinstance(rules, list) or not 1 <= len(rules) <= 100:
        return ScoreOutput(status="error", reason="rules scorer requires 1..100 checks")
    outcomes, refs, reasons = [], set(), []
    for index, rule in enumerate(rules):
        try:
            rule = Check.model_validate(rule).model_dump(exclude_unset=True)
        except ValidationError:
            return ScoreOutput(status="error", reason=f"check {index} has invalid configuration")
        kind = rule.get("kind", "equals")
        if kind in {"equals", "contains"}:
            output = request.result.get("output")
            if output is None:
                return ScoreOutput(
                    status="insufficient_evidence", reason="execution output is missing"
                )
            try:
                actual = pointer(output, rule.get("pointer", ""))
                expected = (
                    rule["value"]
                    if "value" in rule
                    else pointer(request.case.get("expectations", {}), rule["expectation_pointer"])
                )
            except KeyError, IndexError, TypeError, ValueError:
                return ScoreOutput(
                    status="insufficient_evidence",
                    reason=f"check {index} has a missing output or expectation path",
                )
            if kind == "equals":
                passed = json_bytes(actual) == json_bytes(expected)
            elif isinstance(actual, (str, list, dict)):
                try:
                    passed = expected in actual
                except TypeError:
                    return ScoreOutput(
                        status="error", reason=f"check {index} contains operands are incompatible"
                    )
            else:
                return ScoreOutput(
                    status="error", reason=f"check {index} contains requires text or a collection"
                )
            refs.add(f"attempt:{request.attempt_id}:output")
            if "value" not in rule:
                refs.update(
                    ref for ref in request.evidence.references if ref.endswith(":expectations")
                )
        elif kind == "event":
            if request.evidence.status != "sealed" or request.evidence.dropped_events != 0:
                return ScoreOutput(
                    status="insufficient_evidence",
                    reason="event presence scoring requires sealed, loss-free evidence",
                )
            matching = [
                event
                for event in request.evidence.events
                if event.get("type") == rule.get("type")
                and all(event.get("data", {}).get(k) == v for k, v in rule.get("data", {}).items())
            ]
            passed = bool(matching)
            # Event IDs in the view are producer IDs; references use database record IDs.
            refs.update(ref for ref in request.evidence.references if ref.startswith("event:"))
            if not refs:
                return ScoreOutput(
                    status="insufficient_evidence", reason="no event references are available"
                )
        elif kind == "artifact":
            if request.evidence.status != "sealed":
                return ScoreOutput(
                    status="insufficient_evidence",
                    reason="artifact presence scoring requires sealed evidence",
                )
            matching = [
                item
                for item in request.evidence.artifacts
                if item.get("metadata_content", {}).get("name") == rule.get("name")
            ]
            passed = bool(matching)
            for item in matching:
                context.artifact(str(item["id"]))
                refs.add(f"artifact:{item['id']}")
            if not matching:
                observed_missing = any(
                    event.get("type") == "artifact.missing"
                    and event.get("data", {}).get("name") == rule.get("name")
                    for event in request.evidence.events
                )
                if not observed_missing:
                    return ScoreOutput(
                        status="insufficient_evidence",
                        reason="artifact was neither captured nor observed missing",
                    )
                refs.update(ref for ref in request.evidence.references if ref.startswith("event:"))
        else:
            return ScoreOutput(status="error", reason=f"unsupported rule kind: {kind}")
        outcomes.append(passed)
        reasons.append(f"check {index + 1}: {'pass' if passed else 'fail'}")
    value = None
    passed = all(outcomes)
    if request.scorer.numeric:
        semantics = request.scorer.numeric
        fraction = sum(outcomes) / len(outcomes)
        value = semantics.minimum + (semantics.maximum - semantics.minimum) * (
            fraction if semantics.direction == "higher" else 1 - fraction
        )
        passed = (
            value >= semantics.threshold
            if semantics.direction == "higher"
            else value <= semantics.threshold
        )
    return ScoreOutput(
        status="completed",
        verdict="pass" if passed else "fail",
        value=value,
        reason="; ".join(reasons),
        evidence_refs=sorted(refs),
    )
