"""Common audit-event sanitization helpers."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

SENSITIVE_KEY_RE = re.compile(
    r"password|secret|token|cookie|authorization|sequence|report_body|file_content",
    re.IGNORECASE,
)


def safe_audit_metadata(value: Any, *, depth: int = 0) -> Any:
    """Return a bounded, redacted copy suitable for durable audit storage."""
    if depth > 4:
        return "[depth-limited]"
    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in list(value.items())[:50]:
            key_text = str(key)
            safe[key_text] = (
                "[redacted]"
                if SENSITIVE_KEY_RE.search(key_text)
                else safe_audit_metadata(item, depth=depth + 1)
            )
        return safe
    if isinstance(value, (list, tuple, set)):
        return [safe_audit_metadata(item, depth=depth + 1) for item in list(value)[:50]]
    if isinstance(value, str):
        return value[:1000]
    if value is None or isinstance(value, (bool, int, float, datetime)):
        return value
    return str(value)[:1000]
