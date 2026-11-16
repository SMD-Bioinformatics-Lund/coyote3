"""Guardrail tests for API documentation grouping."""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import pytest
from coyote_api.app import extensions
from coyote_api.app.main import create_api_app
from coyote_api.interfaces.http.registry import ROUTERS
from coyote_api.interfaces.http.tags import OPENAPI_TAG_NAMES, TAG_INGESTION, TAG_SYSTEM
from fastapi.routing import APIRoute, iter_route_contexts


@pytest.fixture
def app(monkeypatch):
    """Build the standalone server without optional installed route extensions."""
    monkeypatch.setattr(extensions, "entry_points", lambda **_: ())
    return create_api_app()


def test_openapi_tags_are_registered_in_canonical_order(app):
    """OpenAPI should expose the documented domain taxonomy."""
    schema = app.openapi()
    names = [tag["name"] for tag in schema.get("tags", [])]
    assert names == [name for name in OPENAPI_TAG_NAMES if name != TAG_INGESTION]


def test_api_routes_use_only_registered_openapi_tags(app):
    """Route modules should not introduce ad-hoc OpenAPI tag names."""
    allowed = set(OPENAPI_TAG_NAMES)
    unexpected: list[str] = []
    for route in iter_route_contexts(app.routes):
        if not isinstance(route.original_route, APIRoute):
            continue
        if not route.path.startswith("/api/v1/") or not route.include_in_schema:
            continue
        for tag in route.tags:
            if tag not in allowed:
                unexpected.append(f"{route.path}: {tag}")

    assert not unexpected, "Unexpected API route tags:\n" + "\n".join(unexpected)


def test_openapi_exposes_supported_contract_and_hides_runtime_plumbing(app):
    """The standalone server exposes health without optional ingestion operations."""
    schema = app.openapi()
    paths = set(schema.get("paths", {}))

    assert "/api/v1/health" in paths
    assert schema["paths"]["/api/v1/health"]["get"]["tags"] == [TAG_SYSTEM]
    assert not any(path.startswith("/api/v1/internal/") for path in paths)
    assert "/api/v1/samples" in paths
    assert "/api/v1/admin/controls" in paths
    assert "/api/v1/notifications" not in paths
    assert "/api/v1/notifications/read-all" not in paths
    assert "/api/v1/admin/notifications/recipients" not in paths
    assert "/api/v1/admin/notifications/broadcast" in paths
    assert not any("/admin/demo-installation" in path for path in paths)
    assert "/api/v1/admin/query-rule-sets" in paths
    assert TAG_INGESTION not in {tag["name"] for tag in schema["tags"]}


def test_hidden_routers_remain_registered_at_runtime(app):
    """Schema-hidden routes must remain callable through the application router."""
    hidden_paths = {
        route.path
        for registration in ROUTERS
        if not registration.include_in_schema
        for route in registration.router.routes
    }
    runtime_paths = {getattr(route, "path", "") for route in iter_route_contexts(app.router.routes)}

    assert "/api/v1/health" not in hidden_paths
    assert "/api/v1/internal/metrics" in hidden_paths
    assert "/api/v1/internal/roles/levels" in hidden_paths
    assert "/api/v1/internal/tasks/{task_id}" not in runtime_paths
    assert hidden_paths <= runtime_paths


def test_http_route_modules_live_in_owned_subpackages():
    """The HTTP root should contain registry/taxonomy files, not route modules."""
    allowed_root_files = {"__init__.py", "registry.py", "tags.py", "errors.py"}
    root_files = {
        path.name
        for path in Path(str(files("coyote_api").joinpath("interfaces/http"))).glob("*.py")
    }
    assert root_files == allowed_root_files
