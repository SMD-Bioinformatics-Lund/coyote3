"""Verify that declared React page API contracts resolve to real API routes."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute

from api.app.main import app

REGISTRY_PATH = Path("frontend/src/lib/routes/ui-route-registry.ts")
DECLARED_API_PATTERN = re.compile(r'"(?P<method>GET|POST|PUT|PATCH|DELETE) (?P<path>/[^"]+)"')


def _segments_match(declared_path: str, route_path: str) -> bool:
    """Match UI ``:parameter`` segments against FastAPI ``{parameter}`` segments."""
    declared_segments = [segment for segment in declared_path.strip("/").split("/") if segment]
    route_segments = [segment for segment in route_path.strip("/").split("/") if segment]
    if len(declared_segments) != len(route_segments):
        return False
    return all(
        declared == route
        or declared.startswith(":")
        and route.startswith("{")
        and route.endswith("}")
        for declared, route in zip(declared_segments, route_segments, strict=True)
    )


def _declared_page_api_contracts() -> list[tuple[str, str]]:
    """Read literal API declarations from the frontend route registry."""
    source = REGISTRY_PATH.read_text(encoding="utf-8")
    return [
        (match.group("method"), match.group("path"))
        for match in DECLARED_API_PATTERN.finditer(source)
        if ":resource" not in match.group("path")
    ]


def test_each_literal_page_api_contract_has_a_backend_route() -> None:
    """Prevent UI registry entries from drifting away from documented FastAPI routes."""
    api_routes = [route for route in app.routes if isinstance(route, APIRoute)]
    missing: list[str] = []

    for method, ui_path in _declared_page_api_contracts():
        expected_path = f"/api/v1{ui_path}"
        found = any(
            method in route.methods and _segments_match(expected_path, route.path)
            for route in api_routes
        )
        if not found:
            missing.append(f"{method} {expected_path}")

    assert not missing, "Frontend page registry references missing API routes:\n" + "\n".join(
        missing
    )


def test_route_registry_declares_empty_and_error_behavior_helpers() -> None:
    """Require page contracts to retain explicit empty/error-state guidance."""
    source = REGISTRY_PATH.read_text(encoding="utf-8")
    assert "function routeEmptyState" in source
    assert "function routeErrorState" in source
    assert "uiRouteRegistry" in source
