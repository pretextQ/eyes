"""Compatibility imports for existing integrations; new code uses eyes.common.files."""

from eyes.common.files import (
    SECRET_REFERENCE as SECRET_REFERENCE,
)
from eyes.common.files import (
    atomic_write as atomic_write,
)
from eyes.common.files import (
    error_text as error_text,
)
from eyes.common.files import (
    file_digest as file_digest,
)
from eyes.common.files import (
    json_bytes as json_bytes,
)
from eyes.common.files import (
    redact as redact,
)
from eyes.common.files import (
    resolve_secrets as resolve_secrets,
)
from eyes.common.files import (
    write_json as write_json,
)
