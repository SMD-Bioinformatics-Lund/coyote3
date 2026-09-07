"""Exhaustive authorization contracts for shipped roles, permissions, and API routes."""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Generator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute
from starlette.requests import Request

from api.app.main import app
from api.security import access
from api.security.access import ApiUser
from api.security.policy import build_access_policy

_RBAC_ROOT = Path("api/config/bootstrap/rbac")


def _seed_documents(name: str) -> list[dict[str, Any]]:
    """Load one shipped RBAC catalog without requiring a database."""
    path = _RBAC_ROOT / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _catalog() -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    permissions = {
        str(item["permission_id"]): item
        for item in _seed_documents("permissions.seed.ndjson")
        if item.get("is_active", True)
    }
    roles = {
        str(item["role_id"]): item
        for item in _seed_documents("roles.seed.ndjson")
        if item.get("is_active", True)
    }
    return permissions, roles


def _user(role: dict[str, Any]) -> ApiUser:
    role_id = str(role["role_id"])
    return ApiUser(
        id=f"test-{role_id}",
        email=f"{role_id}@example.org",
        fullname=role_id,
        username=f"test-{role_id}",
        roles=[role_id],
        role=role_id,
        access_level=int(role.get("level") or 0),
        permissions=[],
        asp_ids=["*"],
        asp_groups=["*"],
        envs=["*"],
        asp_map={},
        auth_type=["local"],
    )


def _require_access_dependencies(route: APIRoute) -> list[tuple[Callable[..., Any], str | None]]:
    """Return the exact ``require_access`` dependencies installed on one route."""
    dependencies = list(route.dependant.dependencies)
    found: list[tuple[Callable[..., Any], str | None]] = []
    while dependencies:
        dependency = dependencies.pop()
        dependencies.extend(dependency.dependencies)
        call = dependency.call
        if getattr(call, "__name__", "") != "dep":
            continue
        permission = inspect.getclosurevars(call).nonlocals.get("permission")
        if permission is None or isinstance(permission, str):
            found.append((call, permission))
    return found


def _protected_routes() -> list[tuple[APIRoute, list[tuple[Callable[..., Any], str | None]]]]:
    routes = []
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith("/api/"):
            continue
        dependencies = _require_access_dependencies(route)
        if dependencies:
            routes.append((route, dependencies))
    return routes


def _request(route: APIRoute) -> Request:
    return Request(
        {
            "type": "http",
            "method": sorted(route.methods)[0],
            "path": route.path,
            "headers": [],
        }
    )


def test_every_active_permission_is_granted_by_a_shipped_role() -> None:
    permissions, roles = _catalog()
    granted = {permission for role in roles.values() for permission in role.get("permissions", [])}
    assert not permissions.keys() - granted, "Active permissions without a bundled role grant"


def test_every_role_permission_decision_matches_the_seed_catalog() -> None:
    """Exercise every shipped role against every active permission through Casbin policy."""
    permissions, roles = _catalog()
    roles_repository = SimpleNamespace(get_all_roles=lambda: list(roles.values()))
    permissions_repository = SimpleNamespace(
        get_all_permissions=lambda **_: list(permissions.values())
    )

    for role_id, role in roles.items():
        user = _user(role)
        policy = build_access_policy(
            user=user,
            roles_repository=roles_repository,
            permissions_repository=permissions_repository,
        )
        granted = set(role.get("permissions", []))
        for permission_id in permissions:
            assert policy.permission_allowed(user, permission_id) is (permission_id in granted), (
                f"Role '{role_id}' has an unexpected decision for '{permission_id}'"
            )


def test_every_require_access_endpoint_enforces_the_complete_role_matrix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run each route dependency for every bundled role using its effective policy."""
    permissions, roles = _catalog()
    routes = _protected_routes()
    assert routes, "No require_access-protected API routes were discovered"

    role_users = {role_id: _user(role) for role_id, role in roles.items()}
    roles_repository = SimpleNamespace(get_all_roles=lambda: list(roles.values()))
    permissions_repository = SimpleNamespace(
        get_all_permissions=lambda **_: list(permissions.values())
    )
    policies = {
        role_id: build_access_policy(
            user=user,
            roles_repository=roles_repository,
            permissions_repository=permissions_repository,
        )
        for role_id, user in role_users.items()
    }
    current_user: list[ApiUser] = [next(iter(role_users.values()))]

    monkeypatch.setattr(access, "_decode_session_user", lambda _request: current_user[0])
    monkeypatch.setattr(access, "_audit_access_event", lambda **_: None)
    monkeypatch.setattr(access, "build_access_policy", lambda *, user, **_: policies[user.role])

    for route, dependencies in routes:
        request = _request(route)
        for role_id, role in roles.items():
            current_user[0] = role_users[role_id]
            granted = set(role.get("permissions", []))
            for dependency, permission in dependencies:
                allowed = permission is None or role_id == "superuser" or permission in granted
                generator: Generator[ApiUser, None, None] = dependency(request)
                if allowed:
                    try:
                        assert next(generator) == current_user[0]
                    finally:
                        generator.close()
                    continue
                with pytest.raises(HTTPException) as exc:
                    next(generator)
                assert exc.value.status_code == 403, (
                    f"{role_id} unexpectedly reached {sorted(route.methods)} {route.path} "
                    f"without '{permission}'"
                )


def test_every_protected_endpoint_permission_is_active_and_seeded() -> None:
    permissions, _roles = _catalog()
    unknown: set[str] = set()
    for route, dependencies in _protected_routes():
        for _dependency, permission in dependencies:
            if permission and permission not in permissions:
                unknown.add(f"{sorted(route.methods)} {route.path}: {permission}")
    assert not unknown, "Protected endpoints use unknown or inactive permissions:\n" + "\n".join(
        sorted(unknown)
    )
