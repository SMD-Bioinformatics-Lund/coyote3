"""Guardrail tests for API documentation grouping."""

from __future__ import annotations

from pathlib import Path

from fastapi.routing import APIRoute

from api.app.main import app
from api.interfaces.http.registry import ROUTERS
from api.interfaces.http.tags import OPENAPI_TAG_NAMES


def test_openapi_tags_are_registered_in_canonical_order():
    """OpenAPI should expose the documented domain taxonomy."""
    schema = app.openapi()
    names = [tag["name"] for tag in schema.get("tags", [])]
    assert names == list(OPENAPI_TAG_NAMES)


def test_api_routes_use_only_registered_openapi_tags():
    """Route modules should not introduce ad-hoc OpenAPI tag names."""
    allowed = set(OPENAPI_TAG_NAMES)
    unexpected: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/v1/") or not route.include_in_schema:
            continue
        for tag in route.tags:
            if tag not in allowed:
                unexpected.append(f"{route.path}: {tag}")

    assert not unexpected, "Unexpected API route tags:\n" + "\n".join(unexpected)


def test_openapi_exposes_supported_contract_and_hides_runtime_plumbing():
    """OpenAPI visibility must not expose health or internal integration routes."""
    schema = app.openapi()
    paths = set(schema.get("paths", {}))

    assert "/api/v1/health" not in paths
    assert not any(path.startswith("/api/v1/internal/") for path in paths)
    assert "/api/v1/samples" in paths
    assert "/api/v1/admin/controls" in paths
    assert "/api/v1/notifications" not in paths
    assert "/api/v1/notifications/read-all" not in paths
    assert "/api/v1/admin/notifications/recipients" not in paths
    assert "/api/v1/admin/notifications/broadcast" in paths


def test_hidden_routers_remain_registered_at_runtime():
    """Schema-hidden routes must remain callable through the application router."""
    hidden_paths = {
        route.path
        for registration in ROUTERS
        if not registration.include_in_schema
        for route in registration.router.routes
    }
    runtime_paths = {getattr(route, "path", "") for route in app.router.routes}

    assert "/api/v1/health" in hidden_paths
    assert "/api/v1/internal/metrics" in hidden_paths
    assert "/api/v1/internal/tasks/{task_id}" in hidden_paths
    assert hidden_paths <= runtime_paths


def test_http_route_modules_live_in_owned_subpackages():
    """The HTTP root should contain registry/taxonomy files, not route modules."""
    allowed_root_files = {"__init__.py", "registry.py", "tags.py"}
    root_files = {path.name for path in Path("api/interfaces/http").glob("*.py")}
    assert root_files == allowed_root_files
