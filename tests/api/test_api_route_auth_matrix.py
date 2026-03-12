"""Dynamic auth matrix tests for API routes.

These tests iterate over registered FastAPI routes and verify protected endpoints
fail closed when called without authentication.
"""

from __future__ import annotations

import re
from typing import Iterable

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from api.main import app

_OPEN_EXACT = {
    "/api/v1/health",
    "/api/v1/auth/sessions",
    "/api/v1/auth/sessions/current",
    "/api/v1/docs",
    "/api/v1/openapi.json",
    "/api/v1/redoc",
    "/api/v1/common/gene/{gene_id}/info",
}
_OPEN_PREFIX = ("/api/v1/public/",)
_SKIP_METHODS = {"HEAD", "OPTIONS"}


def _iter_api_routes() -> Iterable[tuple[str, str]]:
    """Handle  iter api routes.

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


def _materialize_path(path: str) -> str:
    """Handle  materialize path.

    Args:
            path: Path.

    Returns:
            The  materialize path result.
    """
    replacements = {
        "sample_id": "SAMPLE1",
        "var_id": "VAR1",
        "fusion_id": "FUS1",
        "comment_id": "COM1",
        "callidx": "0",
        "num_calls": "1",
        "report_id": "RPT1",
        "user_id": "USR1",
        "role_id": "ROLE1",
        "permission_id": "PERM1",
    }

    def repl(match: re.Match[str]) -> str:
        """Handle repl.

        Args:
            match (re.Match[str]): Value for ``match``.

        Returns:
            str: The function result.
        """
        key = match.group(1)
        return replacements.get(key, "X")

    return re.sub(r"\{([^}]+)\}", repl, path)


def _is_open(path: str) -> bool:
    """Handle  is open.

    Args:
            path: Path.

    Returns:
            The  is open result.
    """
    return path in _OPEN_EXACT or path.startswith(_OPEN_PREFIX)


def test_protected_routes_fail_closed_without_auth():
    """Handle test protected routes fail closed without auth.

    Returns:
        The function result.
    """
    client = TestClient(app)
    unexpected: list[str] = []

    for method, route_path in _iter_api_routes():
        if _is_open(route_path):
            continue

        path = _materialize_path(route_path)
        request_kwargs = {}
        if method in {"POST", "PUT", "PATCH"}:
            request_kwargs["json"] = {}

        response = client.request(method, path, **request_kwargs)

        # Expected unauthenticated outcomes for protected routes.
        if response.status_code not in {401, 403, 422}:
            unexpected.append(f"{method} {route_path} -> {response.status_code}")

    assert not unexpected, "Protected routes did not fail closed:\n" + "\n".join(unexpected)
