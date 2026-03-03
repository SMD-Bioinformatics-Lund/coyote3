"""Route-module guardrails for maintainable API organization."""

from __future__ import annotations

from pathlib import Path
import re


ROUTE_RE = re.compile(r'@app\.(?:get|post|put|delete|patch)\("([^"]+)"')
ALLOWED_PREFIXES = ("/api/v1/", "/api/vi/")


def _route_paths(py_file: Path) -> list[str]:
    lines = py_file.read_text(encoding="utf-8").splitlines()
    return [m.group(1) for line in lines if (m := ROUTE_RE.search(line))]


def test_api_route_modules_have_docstrings_and_routes():
    route_files = sorted(Path("api/routes").glob("*.py"))
    missing_docstring: list[str] = []
    missing_routes: list[str] = []

    for route_file in route_files:
        if route_file.name == "__init__.py":
            continue
        text = route_file.read_text(encoding="utf-8")
        if not text.lstrip().startswith('"""'):
            missing_docstring.append(str(route_file))
        if not _route_paths(route_file):
            missing_routes.append(str(route_file))

    assert not missing_docstring, "Route modules missing top-level docstring:\n" + "\n".join(missing_docstring)
    assert not missing_routes, "Route modules without HTTP routes:\n" + "\n".join(missing_routes)


def test_api_routes_use_versioned_prefixes():
    invalid_paths: list[str] = []

    for route_file in sorted(Path("api/routes").glob("*.py")):
        if route_file.name == "__init__.py":
            continue
        for path in _route_paths(route_file):
            if not path.startswith(ALLOWED_PREFIXES):
                invalid_paths.append(f"{route_file}:{path}")

    assert not invalid_paths, "Routes with non-versioned prefixes found:\n" + "\n".join(invalid_paths)
