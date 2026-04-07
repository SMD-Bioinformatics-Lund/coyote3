"""Regression tests for DNA blacklist-override UI actions."""

from __future__ import annotations

import importlib

import coyote
from coyote import init_app


class _FakeApiClient:
    """Capture outgoing API calls for variant action routes."""

    def __init__(self) -> None:
        """Initialize capture storage."""
        self.calls: list[tuple[str, str, dict | None]] = []

    def patch_json(self, path: str, headers=None, json_body=None):  # noqa: ANN001
        """Record a PATCH call."""
        self.calls.append(("PATCH", path, json_body))
        return {"status": "ok"}

    def delete_json(self, path: str, headers=None, json_body=None):  # noqa: ANN001
        """Record a DELETE call."""
        self.calls.append(("DELETE", path, json_body))
        return {"status": "ok"}


def _load_action_views():
    """Import the DNA action view module with external API checks disabled."""
    original_verify = coyote.verify_external_api_dependency
    coyote.verify_external_api_dependency = lambda _app: None
    try:
        app = init_app(testing=True)
    finally:
        coyote.verify_external_api_dependency = original_verify

    with app.app_context():
        module = importlib.import_module("coyote.blueprints.dna.views_small_variant_actions")
    return app, module


def test_blacklist_override_actions_call_expected_api_endpoints(monkeypatch):
    """Override and clear-blacklist actions should call the canonical API routes."""
    app, views = _load_action_views()
    client = _FakeApiClient()

    monkeypatch.setattr(views, "get_web_api_client", lambda: client)
    monkeypatch.setattr(views, "forward_headers", lambda: {"X-Test": "1"})

    with app.test_request_context("/dna/S1/var/v1/override_blacklist", method="POST"):
        response = views.override_variant_blacklist.__wrapped__("S1", "v1")
    assert response.status_code == 302
    assert response.location.endswith("/dna/S1/var/v1")

    with app.test_request_context("/dna/S1/var/v1/clear_override_blacklist", method="POST"):
        response = views.clear_variant_blacklist_override.__wrapped__("S1", "v1")
    assert response.status_code == 302
    assert response.location.endswith("/dna/S1/var/v1")

    assert client.calls == [
        ("PATCH", "/api/v1/samples/S1/small-variants/v1/flags/override-blacklist", None),
        ("DELETE", "/api/v1/samples/S1/small-variants/v1/flags/override-blacklist", None),
    ]
