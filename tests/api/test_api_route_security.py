"""Guardrail tests for API router protection boundaries."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROUTE_RE = re.compile(r'@(?:app|router)\.(?:get|post|put|delete|patch)\("([^"]+)"')
DEF_RE = re.compile(r"^\s*def\s+")

# Public and auth-bootstrap endpoints intentionally do not require user RBAC.
ALLOW_UNGUARDED_EXACT = {
    "/api/v1/health",
    "/api/v1/auth/providers",
    "/api/v1/auth/sessions",
    "/api/v1/auth/sessions/current",
    "/api/v1/auth/password/reset/request",
    "/api/v1/auth/password/reset/confirm",
}
ALLOW_UNGUARDED_PREFIX = ("/api/v1/public/",)


def _iter_route_decorators(py_file: Path):
    """Iter route decorators.

    Args:
            py_file: Py file.

    Returns:
            The  iter route decorators result.
    """
    lines = py_file.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines):
        match = ROUTE_RE.search(line)
        if match:
            yield lines, idx, match.group(1)


def _is_guarded(lines: list[str], decorator_idx: int) -> bool:
    """Is guarded.

    Args:
            lines: Lines.
            decorator_idx: Decorator idx.

    Returns:
            The  is guarded result.
    """
    i = decorator_idx + 1
    while i < len(lines) and not DEF_RE.match(lines[i]):
        i += 1
    if i >= len(lines):
        return False
    block = "\n".join(lines[i : i + 35])
    return ("require_access(" in block) or ("_require_internal_token(" in block)


def test_non_public_api_routes_are_guarded():
    """Test non public api routes are guarded.

    Returns:
        The function result.
    """
    route_files = sorted(Path("api/interfaces/http").rglob("*.py"))
    unguarded: list[str] = []

    for py_file in route_files:
        for lines, idx, path in _iter_route_decorators(py_file):
            if path in ALLOW_UNGUARDED_EXACT or path.startswith(ALLOW_UNGUARDED_PREFIX):
                continue
            if not _is_guarded(lines, idx):
                unguarded.append(f"{py_file}:{path}")

    assert not unguarded, "Unguarded API routes found:\n" + "\n".join(unguarded)


def test_declared_route_permissions_exist_in_seed_catalog():
    """Every permission referenced by a route must be deployable from the RBAC catalog."""
    permission_pattern = re.compile(r'require_access\(\s*permission\s*=\s*["\']([^"\']+)["\']')
    declared: set[str] = set()
    for route_file in Path("api/interfaces/http").rglob("*.py"):
        declared.update(permission_pattern.findall(route_file.read_text(encoding="utf-8")))

    with Path("api/config/bootstrap/rbac/permissions.seed.ndjson").open(
        "rt", encoding="utf-8"
    ) as handle:
        catalog = {
            str(json.loads(line)["permission_id"]).strip().lower()
            for line in handle
            if line.strip()
        }

    assert declared <= catalog, f"Route permissions missing from seed catalog: {declared - catalog}"


def test_seeded_role_grants_reference_known_permissions():
    """Built-in roles must not contain grants absent from the permission catalog."""
    with Path("api/config/bootstrap/rbac/permissions.seed.ndjson").open(
        "rt", encoding="utf-8"
    ) as handle:
        catalog = {
            str(json.loads(line)["permission_id"]).strip().lower()
            for line in handle
            if line.strip()
        }
    with Path("api/config/bootstrap/rbac/roles.seed.ndjson").open("rt", encoding="utf-8") as handle:
        role_docs = [json.loads(line) for line in handle if line.strip()]

    unknown = {
        permission
        for role in role_docs
        for permission in role.get("permissions", [])
        if permission not in catalog
    }
    assert not unknown, f"Built-in roles reference unknown permissions: {unknown}"
