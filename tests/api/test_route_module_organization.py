"""HTTP module guardrails for maintainable API organization."""

from __future__ import annotations

from pathlib import Path
import re


ROUTE_RE = re.compile(r'@(?:app|router)\.(?:get|post|put|delete|patch)\("([^"]+)"')
ALLOWED_PREFIXES = ("/api/v1/", "/api/vi/")


def _route_paths(py_file: Path) -> list[str]:
    """Handle  route paths.

    Args:
            py_file: Py file.

    Returns:
            The  route paths result.
    """
    lines = py_file.read_text(encoding="utf-8").splitlines()
    return [m.group(1) for line in lines if (m := ROUTE_RE.search(line))]


def _canonical_http_modules() -> list[Path]:
    """Handle  canonical http modules.

    Returns:
            The  canonical http modules result.
    """
    modules: list[Path] = []
    for path in sorted(Path("api/routers").glob("*.py")):
        if path.name in {"__init__.py", "registry.py"}:
            continue
        text = path.read_text(encoding="utf-8")
        if "APIRouter(" in text or "@router." in text:
            modules.append(path)
    return modules


def test_api_router_modules_have_docstrings_and_routes():
    """Handle test api router modules have docstrings and routes.

    Returns:
        The function result.
    """
    route_files = _canonical_http_modules()
    missing_docstring: list[str] = []
    missing_routes: list[str] = []

    for route_file in route_files:
        text = route_file.read_text(encoding="utf-8")
        if not text.lstrip().startswith('"""'):
            missing_docstring.append(str(route_file))
        if not _route_paths(route_file):
            missing_routes.append(str(route_file))

    assert not missing_docstring, "Router modules missing top-level docstring:\n" + "\n".join(missing_docstring)
    assert not missing_routes, "Router modules without HTTP routes:\n" + "\n".join(missing_routes)


def test_api_routes_use_versioned_prefixes():
    """Handle test api routes use versioned prefixes.

    Returns:
        The function result.
    """
    invalid_paths: list[str] = []

    for route_file in _canonical_http_modules():
        for path in _route_paths(route_file):
            if not path.startswith(ALLOWED_PREFIXES):
                invalid_paths.append(f"{route_file}:{path}")

    assert not invalid_paths, "Routes with non-versioned prefixes found:\n" + "\n".join(invalid_paths)
