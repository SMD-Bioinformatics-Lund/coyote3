"""Pure interpretation of operational policy values supplied by an application host."""

from collections.abc import Mapping
from typing import Any


def get_audit_retention_days(config: Mapping[str, Any]) -> int:
    """Return audit retention in days."""
    try:
        return int(config.get("AUDIT_RETENTION_DAYS", 730))
    except (TypeError, ValueError):
        return 730


def get_runtime_environment(config: Mapping[str, Any]) -> str:
    """Return the normalized runtime environment label."""
    env_name = str(config.get("ENV_NAME") or "production").strip().lower()
    if env_name in {"dev", "development"}:
        return "development"
    if env_name in {"test", "testing"}:
        return "test"
    if env_name in {"stage", "staging"}:
        return "staging"
    return env_name or "production"
