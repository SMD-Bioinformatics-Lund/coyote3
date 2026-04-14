"""Web UI rate-limit behavior tests."""

from __future__ import annotations

import coyote
from coyote import init_app
from coyote.services.api_client.api_client import CoyoteApiClient
from coyote.services.api_client.base import ApiPayload


def test_ui_rate_limit_returns_429_and_retry_after(monkeypatch):
    """When UI limit is exceeded, Flask before-request should return 429."""

    def _fake_get(self, path, headers=None, params=None):  # noqa: ARG001
        if path.endswith("/internal/roles/levels"):
            return ApiPayload({"role_levels": {}})
        return ApiPayload({})

    monkeypatch.setattr(coyote, "verify_external_api_dependency", lambda _app: None)
    monkeypatch.setattr(CoyoteApiClient, "get_json", _fake_get)

    app = init_app(testing=True)
    app.config.update(
        WEB_RATE_LIMIT_ENABLED=True,
        WEB_RATE_LIMIT_REQUESTS_PER_MINUTE=1,
        WEB_RATE_LIMIT_WINDOW_SECONDS=60,
    )
    client = app.test_client()

    first = client.get("/_rate_limit_probe")
    second = client.get("/_rate_limit_probe")

    assert first.status_code == 404
    assert second.status_code == 429
    assert second.headers.get("Retry-After") is not None
    assert second.headers.get("X-Request-ID")
    assert b"Too many requests" in second.data
