"""Redact recognizable credentials before diagnostics leave the process."""

from __future__ import annotations

import re
from typing import Any

SENSITIVE_KEY_RE = re.compile(
    r"password|passwd|secret|token|cookie|authorization|api[_-]?key|sequence|report_body|file_content",
    re.IGNORECASE,
)
_URL_CREDENTIALS = re.compile(r"([a-z][a-z0-9+.-]*://)[^\s/@]+(?::[^\s/@]*)?@", re.I)
_BEARER = re.compile(r"\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]+", re.I)
_ASSIGNMENT = re.compile(
    r"(?i)(\b(?:password|passwd|secret|token|access_token|refresh_token|api[_-]?key|authorization|cookie)"
    r"[\"']?\s*[:=]\s*)(?:\"[^\"]*\"|'[^']*'|[^\s,;&}]+)"
)


def redact_text(value: str) -> str:
    """Replace URI credentials, authentication headers and named secret assignments.

    Args:
        value: Diagnostic text, never a source of clinical or persisted business data.

    Returns:
        Scrubbed text. Arbitrary identifiers and unlabeled secrets cannot be recognized.
    """
    value = _URL_CREDENTIALS.sub(r"\1[redacted]@", value)
    value = _BEARER.sub(r"\1 [redacted]", value)
    return _ASSIGNMENT.sub(r"\1[redacted]", value)


def redact_diagnostics(value: Any) -> Any:
    """Scrub diagnostic mappings, sequences and text without changing their source.

    Args:
        value: JSON-like diagnostic data; other scalar types are preserved.

    Returns:
        Copy with sensitive mapping values and recognizable text credentials removed.
    """
    if isinstance(value, dict):
        return {
            key: "[redacted]" if SENSITIVE_KEY_RE.search(str(key)) else redact_diagnostics(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_diagnostics(item) for item in value]
    return redact_text(value) if isinstance(value, str) else value
