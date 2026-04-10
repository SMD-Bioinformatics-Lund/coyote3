"""Shared helpers for management and configuration services."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from api.contracts.managed_resources import ManagedResourceSpec
from api.contracts.managed_ui_schemas import build_form_spec
from api.extensions import util
from api.runtime_state import current_username
from api.services.common.change_payload import change_payload as _change_payload


def _normalize_permission_id(permission_id: Any) -> str:
    """Normalize a permission identifier for consistent comparisons."""
    return str(permission_id or "").strip().lower()


def normalize_permission_ids(permission_ids: Any) -> list[str]:
    """Normalize a permission-id collection to unique canonical values."""
    normalized: list[str] = []
    seen: set[str] = set()
    if permission_ids is None:
        return normalized
    if isinstance(permission_ids, (str, bytes)):
        permission_ids = [permission_ids]
    for permission_id in permission_ids:
        normalized_id = _normalize_permission_id(permission_id)
        if normalized_id and normalized_id not in seen:
            normalized.append(normalized_id)
            seen.add(normalized_id)
    return normalized


def change_payload(
    *, resource: str, resource_id: str, action: str, sample_id: str = "admin"
) -> dict[str, Any]:
    """Build the standard admin change response payload."""
    return _change_payload(
        sample_id=sample_id, resource=resource, resource_id=resource_id, action=action
    )


def current_actor(default_username: str) -> str:
    """Return the current username or a fallback actor value.

    Args:
        default_username: Username to use when request context has no actor.

    Returns:
        str: Resolved actor username.
    """
    return current_username(default=default_username)


def utc_now() -> datetime:
    """Return the current UTC timestamp.

    Returns:
        datetime: Current UTC timestamp.
    """
    return util.common.utc_now()


def build_managed_form(
    spec: ManagedResourceSpec,
    *,
    actor_username: str | None = None,
) -> dict[str, Any]:
    """Build a managed form payload with optional actor defaults."""
    form = deepcopy(build_form_spec(spec))
    if actor_username:
        actor = current_actor(actor_username)
        now = utc_now()
        for field_name, value in {
            "created_by": actor,
            "created_on": now,
            "updated_by": actor,
            "updated_on": now,
        }.items():
            if field_name in form.get("fields", {}):
                form["fields"][field_name]["default"] = value
    return form


def normalize_managed_form_payload(
    spec: ManagedResourceSpec, form_data: dict[str, Any]
) -> dict[str, Any]:
    """Normalize submitted form data using the managed resource form."""
    return util.records.normalize_form_payload(form_data, build_form_spec(spec))


def lower(value: Any) -> str:
    """Normalize a value to lowercase trimmed text.

    Args:
        value: Value to normalize.

    Returns:
        str: Lowercased string representation.
    """
    return str(value or "").strip().lower()


def role_permission_overrides(
    *,
    role_map: dict[str, dict[str, Any]],
    role_names: list[str] | None,
    permissions: list[str] | None,
    deny_permissions: list[str] | None,
) -> tuple[list[str], list[str]]:
    """Compute permissions granted outside the selected role defaults.

    Args:
        role_map: Role metadata keyed by role name.
        role_names: Selected role names.
        permissions: Requested allow-list overrides.
        deny_permissions: Requested deny-list overrides.

    Returns:
        tuple[list[str], list[str]]: Explicit allow and deny permission overrides.
    """
    requested_permissions = normalize_permission_ids(permissions or [])
    requested_denied_permissions = normalize_permission_ids(deny_permissions or [])
    selected_role_names = [str(role_name or "").strip().lower() for role_name in (role_names or [])]
    role_allow_permissions = normalize_permission_ids(
        permission_id
        for role_name in selected_role_names
        for permission_id in role_map.get(role_name, {}).get("permissions", [])
    )
    role_deny_permissions = normalize_permission_ids(
        permission_id
        for role_name in selected_role_names
        for permission_id in role_map.get(role_name, {}).get("deny_permissions", [])
    )
    explicit_permissions = list(set(requested_permissions) - set(role_allow_permissions))
    explicit_deny_permissions = list(set(requested_denied_permissions) - set(role_deny_permissions))
    return explicit_permissions, explicit_deny_permissions


def inject_version_history(
    *,
    actor_username: str,
    new_config: dict[str, Any],
    old_config: dict[str, Any] | None = None,
    is_new: bool,
) -> dict[str, Any]:
    """Attach version history metadata to a managed config payload.

    Args:
        actor_username: User recording the change.
        new_config: Updated config payload.
        old_config: Existing config payload when updating.
        is_new: Whether the config is being created.

    Returns:
        dict[str, Any]: Config payload with version history metadata.
    """
    return util.records.inject_version_history(
        actor_username=actor_username,
        new_config=deepcopy(new_config),
        old_config=old_config,
        is_new=is_new,
    )


def admin_list_pagination(*, q: str, page: int, per_page: int, total: int) -> dict[str, Any]:
    """Build normalized pagination metadata for admin list payloads."""
    return {
        "q": str(q or ""),
        "page": max(1, int(page or 1)),
        "per_page": max(1, int(per_page or 1)),
        "total": max(0, int(total or 0)),
        "has_next": (max(1, int(page or 1)) * max(1, int(per_page or 1))) < max(0, int(total or 0)),
    }
