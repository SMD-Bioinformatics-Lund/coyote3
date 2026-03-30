"""Dynamic auth matrix tests for API routes.

These tests iterate over registered FastAPI routes and verify protected endpoints
fail closed when called without authentication.
"""

from __future__ import annotations

from typing import Iterable

from fastapi.routing import APIRoute

from api.main import app

_OPEN_EXACT = {
    "/api/v1/health",
    "/api/v1/auth/sessions",
    "/api/v1/auth/sessions/current",
    "/api/v1/auth/password/reset/request",
    "/api/v1/auth/password/reset/confirm",
    "/api/v1/docs",
    "/api/v1/openapi.json",
    "/api/v1/redoc",
    "/api/v1/common/gene/{gene_id}/info",
}
_OPEN_PREFIX = ("/api/v1/public/", "/api/v1/internal/")
_SKIP_METHODS = {"HEAD", "OPTIONS"}


def _iter_api_routes() -> Iterable[tuple[str, str]]:
    """Iter api routes.

    Returns:
            The  iter api routes result.
    """
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        path = route.path
        if not path.startswith("/api/v1/"):
            continue
        for method in sorted(route.methods or set()):
            if method in _SKIP_METHODS:
                continue
            yield method, path


def _is_open(path: str) -> bool:
    """Is open.

    Args:
            path: Path.

    Returns:
            The  is open result.
    """
    return path in _OPEN_EXACT or path.startswith(_OPEN_PREFIX)


def test_protected_routes_fail_closed_without_auth():
    """Test protected routes fail closed without auth.

    Returns:
        The function result.
    """
    unexpected: list[str] = []

    for method, route_path in _iter_api_routes():
        if _is_open(route_path):
            continue

        route = next(
            (
                entry
                for entry in app.routes
                if isinstance(entry, APIRoute)
                and entry.path == route_path
                and method in (entry.methods or set())
            ),
            None,
        )
        assert route is not None
        dep_names = {
            getattr(dep.call, "__name__", "")
            for dep in getattr(route.dependant, "dependencies", [])
            if getattr(dep, "call", None) is not None
        }
        if not dep_names.intersection({"dep", "_require_internal_token", "require_authenticated"}):
            unexpected.append(f"{method} {route_path} -> dependencies={sorted(dep_names)}")

    assert not unexpected, "Protected routes missing auth dependency:\n" + "\n".join(unexpected)
