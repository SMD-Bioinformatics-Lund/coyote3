"""Guardrail tests for API documentation grouping."""

from __future__ import annotations

from pathlib import Path

from fastapi.routing import APIRoute

from api.app.main import app
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
        if not route.path.startswith("/api/v1/"):
            continue
        for tag in route.tags:
            if tag not in allowed:
                unexpected.append(f"{route.path}: {tag}")

    assert not unexpected, "Unexpected API route tags:\n" + "\n".join(unexpected)


def test_http_route_modules_live_in_owned_subpackages():
    """The HTTP root should contain registry/taxonomy files, not route modules."""
    allowed_root_files = {"__init__.py", "registry.py", "tags.py"}
    root_files = {path.name for path in Path("api/interfaces/http").glob("*.py")}
    assert root_files == allowed_root_files
