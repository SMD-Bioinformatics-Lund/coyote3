"""Audit-resource metadata for managed administrative mutations."""

from __future__ import annotations

from typing import Any

from fastapi import Request


def set_managed_resource_audit_context(
    request: Request,
    *,
    resource_type: str,
    action: str,
    result: dict[str, Any],
) -> None:
    """Attach a domain resource descriptor used by the mutation audit middleware."""
    resource_id = str(result.get("resource_id") or "unknown")
    resource_label = resource_type.upper() if resource_type == "aspc" else resource_type
    request.state.audit_resource = {
        "type": resource_type,
        "id": resource_id,
        "name": resource_id,
        "message": f"{action.capitalize()} {resource_label} {resource_id}",
        "metadata": {"action": action, "resource_key": resource_id},
    }
