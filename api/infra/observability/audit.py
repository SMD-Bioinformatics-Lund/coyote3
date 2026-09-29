"""Common audit-event sanitization helpers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from api.infra.observability.redaction import SENSITIVE_KEY_RE, redact_text


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
        return redact_text(value)[:1000]
    if value is None or isinstance(value, (bool, int, float, datetime)):
        return value
    return redact_text(str(value))[:1000]
