"""Guardrail tests for API route protection boundaries."""

from __future__ import annotations

from pathlib import Path
import re


ROUTE_RE = re.compile(r'@app\.(?:get|post|put|delete|patch)\("([^"]+)"')
DEF_RE = re.compile(r"^\s*def\s+")

# Public and auth-bootstrap endpoints intentionally do not require user RBAC.
ALLOW_UNGUARDED_EXACT = {
    "/api/v1/health",
    "/api/vi/docs",
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
}
ALLOW_UNGUARDED_PREFIX = ("/api/v1/public/",)


def _iter_route_decorators(py_file: Path):
    lines = py_file.read_text(encoding="utf-8").splitlines()
    for idx, line in enumerate(lines):
        match = ROUTE_RE.search(line)
        if match:
            yield lines, idx, match.group(1)


def _is_guarded(lines: list[str], decorator_idx: int) -> bool:
    i = decorator_idx + 1
    while i < len(lines) and not DEF_RE.match(lines[i]):
        i += 1
    if i >= len(lines):
        return False
    block = "\n".join(lines[i : i + 35])
    return ("require_access(" in block) or ("_require_internal_token(" in block)


def test_non_public_api_routes_are_guarded():
    route_files = sorted(Path("api/routes").glob("*.py"))
    unguarded: list[str] = []

    for py_file in route_files:
        for lines, idx, path in _iter_route_decorators(py_file):
            if path in ALLOW_UNGUARDED_EXACT or path.startswith(ALLOW_UNGUARDED_PREFIX):
                continue
            if not _is_guarded(lines, idx):
                unguarded.append(f"{py_file}:{path}")

    assert not unguarded, "Unguarded API routes found:\n" + "\n".join(unguarded)
