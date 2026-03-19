"""Shared helpers for management and configuration services."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.extensions import util
from api.runtime import current_username


def mutation_payload(
    *, resource: str, resource_id: str, action: str, sample_id: str = "admin"
) -> dict[str, Any]:
    """Mutation payload.

    Args:
        resource (str): Value for ``resource``.
        resource_id (str): Value for ``resource_id``.
        action (str): Value for ``action``.
        sample_id (str): Value for ``sample_id``.

    Returns:
        dict[str, Any]: The function result.
    """
    return {
        "status": "ok",
        "sample_id": str(sample_id),
        "resource": resource,
        "resource_id": str(resource_id),
        "action": action,
        "meta": {"status": "updated"},
    }


def current_actor(default_username: str) -> str:
    """Current actor.

    Args:
        default_username (str): Value for ``default_username``.

    Returns:
        str: The function result.
    """
    return current_username(default=default_username)


def utc_now() -> str:
    """Utc now.

    Returns:
        str: The function result.
    """
    return util.common.utc_now()


def lower(value: Any) -> str:
    """Lower.

    Args:
        value (Any): Value for ``value``.

    Returns:
        str: The function result.
    """
    return str(value or "").strip().lower()


def role_permission_overrides(
    *,
    role_map: dict[str, dict[str, Any]],
    role_name: str | None,
    permissions: list[str] | None,
    deny_permissions: list[str] | None,
) -> tuple[list[str], list[str]]:
    """Role permission overrides.

    Args:
        role_map (dict[str, dict[str, Any]]): Value for ``role_map``.
        role_name (str | None): Value for ``role_name``.
        permissions (list[str] | None): Value for ``permissions``.
        deny_permissions (list[str] | None): Value for ``deny_permissions``.

    Returns:
        tuple[list[str], list[str]]: The function result.
    """
    role_permissions = role_map.get(role_name or "", {})
    explicit_permissions = list(
        set(permissions or []) - set(role_permissions.get("permissions", []))
    )
    explicit_deny_permissions = list(
        set(deny_permissions or []) - set(role_permissions.get("deny_permissions", []))
    )
    return explicit_permissions, explicit_deny_permissions


def inject_version_history(
    *,
    actor_username: str,
    new_config: dict[str, Any],
    old_config: dict[str, Any] | None = None,
    is_new: bool,
) -> dict[str, Any]:
    """Inject version history.

    Args:
        actor_username (str): Value for ``actor_username``.
        new_config (dict[str, Any]): Value for ``new_config``.
        old_config (dict[str, Any] | None): Value for ``old_config``.
        is_new (bool): Value for ``is_new``.

    Returns:
        dict[str, Any]: The function result.
    """
    return util.admin.inject_version_history(
        user_email=actor_username,
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
