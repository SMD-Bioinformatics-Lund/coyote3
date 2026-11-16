"""Startup-path tests for the canonical API entrypoint."""

from __future__ import annotations

from coyote_api.app.main import app
from fastapi.routing import iter_route_contexts


def test_canonical_api_entrypoint_serves_health():
    route = next(
        (
            entry
            for entry in iter_route_contexts(app.router.routes)
            if getattr(entry, "path", "") == "/api/v1/health"
            and "GET" in getattr(entry, "methods", set())
        ),
        None,
    )

    assert route is not None
    assert route.endpoint() == {"status": "ok"}
