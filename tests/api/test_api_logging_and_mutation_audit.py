"""API request-id correlation and mutation-audit tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api import middleware
from api.deps.repositories import get_sample_repository
from api.main import app
from api.security import access
from api.security.access import ApiUser


def _user(level: int = 9) -> ApiUser:
    """User.

    Args:
            level: Level. Optional argument.

    Returns:
            The  user result.
    """
    return ApiUser(
        id="U1",
        email="user@example.org",
        fullname="User Example",
        username="user1",
        role="user",
        access_level=level,
        permissions=[],
        denied_permissions=[],
        assays=["DNA", "RNA"],
        assay_groups=[],
        envs=["production"],
        asp_map={},
    )


def test_api_response_includes_request_id_header(monkeypatch: pytest.MonkeyPatch):
    """Test api response includes request id header.

    Args:
        monkeypatch (pytest.MonkeyPatch): Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(access, "_decode_session_user", lambda _request: _user(level=9))
    monkeypatch.setattr(access, "_role_levels", lambda: {"user": 9})
    monkeypatch.setitem(
        app.dependency_overrides,
        get_sample_repository,
        lambda: SimpleNamespace(blacklist_coord=lambda *args, **kwargs: None),
    )

    client = TestClient(app)
    response = client.post(
        "/api/v1/coverage/blacklist/entries",
        headers={"X-Request-ID": "rid-123"},
        json={"gene": "TP53", "coord": "17:1-2", "region": "coding", "smp_grp": "G"},
    )

    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == "rid-123"


def test_mutation_event_emits_request_id_user_and_target(monkeypatch: pytest.MonkeyPatch):
    """Test mutation event emits request id user and target.

    Args:
        monkeypatch (pytest.MonkeyPatch): Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    captured: dict = {}

    def _capture_mutation_event(**kwargs):
        """Capture mutation event.

        Args:
                **kwargs: Kwargs. Additional keyword arguments.

        Returns:
                The  capture mutation event result.
        """
        captured.update(kwargs)

    monkeypatch.setattr(access, "_decode_session_user", lambda _request: _user(level=9))
    monkeypatch.setattr(access, "_role_levels", lambda: {"user": 9})
    monkeypatch.setitem(
        app.dependency_overrides,
        get_sample_repository,
        lambda: SimpleNamespace(blacklist_coord=lambda *args, **kwargs: None),
    )
    monkeypatch.setattr(middleware, "emit_mutation_event", _capture_mutation_event)

    client = TestClient(app)
    response = client.post(
        "/api/v1/coverage/blacklist/entries",
        headers={"X-Request-ID": "rid-456"},
        json={"gene": "TP53", "coord": "17:1-2", "region": "coding", "smp_grp": "G"},
    )

    assert response.status_code == 200
    assert captured["username"] == "user1"
    assert captured["action"] == "POST"
    assert captured["target"] == "/api/v1/coverage/blacklist/entries"
    assert captured["request"].headers.get("X-Request-ID") == "rid-456"
