"""Optional cancellation intent; an absent body remains supported."""

import re
import unicodedata

from pydantic import Field, field_validator

from eyes.contracts.base import Contract


class CancellationRequest(Contract):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def displayable_reason(cls, value):
        if value is None:
            return None
        # Plain text only; discard invisible controls and bidi overrides.
        text = "".join(
            char for char in value if not unicodedata.category(char).startswith("C")
        ).strip()
        # Free text is never a credential transport. Mask recognizable token forms.
        return (
            re.sub(
                r"(?i)\b(?:bearer\s+\S+|eyes_[A-Za-z0-9_-]+|sk-[A-Za-z0-9_-]+)",
                "[redacted]",
                text,
            )[:1000]
            or None
        )
