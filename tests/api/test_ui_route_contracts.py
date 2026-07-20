"""Contract checks between the React route registry and FastAPI routes."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi.routing import APIRoute

from api.app.main import app

ROUTE_REGISTRY = Path("frontend/src/lib/routes/ui-route-registry.ts")


def _registry_text() -> str:
    return ROUTE_REGISTRY.read_text(encoding="utf-8")


def _extract_route_blocks(text: str) -> list[str]:
    return re.findall(r"\{\n\s+path:\s+\"[^\"]+\".*?\n\s+\}", text, flags=re.DOTALL)


def _extract_string_field(block: str, field: str) -> str | None:
    match = re.search(rf"{field}:\s+\"([^\"]+)\"", block)
    return match.group(1) if match else None


def _extract_api_entries(block: str) -> list[str]:
    match = re.search(r"api:\s+\[(.*?)\]", block, flags=re.DOTALL)
    if not match:
        return []
    return re.findall(r"\"([A-Z]+ [^\"]+)\"", match.group(1))


def _path_shape(path: str) -> str:
    path = path.split("?", 1)[0]
    path = re.sub(r":[A-Za-z0-9_]+", "{}", path)
    path = re.sub(r"\{[^}]+\}", "{}", path)
    return path.rstrip("/") or "/"


def _api_route_shapes() -> set[tuple[str, str]]:
    shapes: set[tuple[str, str]] = set()
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not route.path.startswith("/api/v1/"):
            continue
        for method in route.methods or set():
            if method in {"HEAD", "OPTIONS"}:
                continue
            shapes.add((method, _path_shape(route.path.removeprefix("/api/v1"))))
    return shapes


def test_ui_route_registry_has_page_level_contract_metadata():
    """Every UI route should declare what it loads and how empty/error states behave."""
    blocks = _extract_route_blocks(_registry_text())
    assert blocks, "No UI route registry entries found"

    seen_paths: set[str] = set()
    missing: list[str] = []
    for block in blocks:
        path = _extract_string_field(block, "path")
        page = _extract_string_field(block, "page")
        area = _extract_string_field(block, "area")
        if not path or not page or not area:
            missing.append(block[:120])
            continue
        if path in seen_paths:
            missing.append(f"duplicate route path: {path}")
        seen_paths.add(path)
        if "dataUsed:" not in block:
            missing.append(f"{path}: missing dataUsed")

    assert not missing, "Invalid UI route metadata:\n" + "\n".join(missing)


def test_ui_route_registry_api_dependencies_exist_in_fastapi():
    """Documented concrete UI API dependencies should map to existing FastAPI routes."""
    api_shapes = _api_route_shapes()
    missing: list[str] = []
    for block in _extract_route_blocks(_registry_text()):
        page_path = _extract_string_field(block, "path") or "<unknown>"
        for entry in _extract_api_entries(block):
            method, endpoint = entry.split(" ", 1)
            if endpoint.startswith("/:"):
                continue
            shape = (method, _path_shape(endpoint))
            if shape not in api_shapes:
                missing.append(f"{page_path}: {method} {endpoint}")

    assert not missing, "UI registry references missing API routes:\n" + "\n".join(missing)
