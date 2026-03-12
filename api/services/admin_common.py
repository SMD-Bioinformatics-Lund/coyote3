"""Shared helpers for admin services."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.extensions import util
from api.runtime import current_username


def mutation_payload(*, resource: str, resource_id: str, action: str, sample_id: str = "admin") -> dict[str, Any]:
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


def current_actor(default_username: str) -> str:
    return current_username(default=default_username)


def utc_now() -> str:
    return util.common.utc_now()


def lower(value: Any) -> str:
    return str(value or "").strip().lower()


def role_permission_overrides(
    *,
    role_map: dict[str, dict[str, Any]],
    role_name: str | None,
    permissions: list[str] | None,
    deny_permissions: list[str] | None,
) -> tuple[list[str], list[str]]:
    role_permissions = role_map.get(role_name or "", {})
    explicit_permissions = list(set(permissions or []) - set(role_permissions.get("permissions", [])))
    explicit_deny_permissions = list(
        set(deny_permissions or []) - set(role_permissions.get("deny_permissions", []))
    )
    return explicit_permissions, explicit_deny_permissions


def inject_version_history(*, actor_username: str, new_config: dict[str, Any], old_config: dict[str, Any] | None = None, is_new: bool) -> dict[str, Any]:
    return util.admin.inject_version_history(
        user_email=actor_username,
        new_config=deepcopy(new_config),
        old_config=old_config,
        is_new=is_new,
    )
