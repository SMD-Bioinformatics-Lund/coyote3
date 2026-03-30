"""Startup-path tests for the canonical API entrypoint."""

from __future__ import annotations

from api.main import app


def test_canonical_api_entrypoint_serves_health():
    """Test canonical api entrypoint serves health.

    Returns:
        The function result.
    """
    route = next(
        (
            entry
            for entry in app.router.routes
            if getattr(entry, "path", "") == "/api/v1/health"
            and "GET" in getattr(entry, "methods", set())
        ),
        None,
    )

    assert route is not None
    assert route.endpoint() == {"status": "ok"}
