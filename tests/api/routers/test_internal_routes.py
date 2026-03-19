"""Behavior tests for internal API routes."""

from __future__ import annotations

from types import SimpleNamespace

from api.routers import internal


def test_get_role_levels_internal_returns_id_to_level_map(monkeypatch):
    """Handle test get role levels internal returns id to level map.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    calls = {"token": 0}

    monkeypatch.setattr(
        internal, "_require_internal_token", lambda _request: calls.__setitem__("token", 1)
    )
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    repository = SimpleNamespace(
        get_all_roles=lambda: [{"role_id": "admin", "level": 99}, {"role_id": "viewer"}]
    )

    payload = internal.get_role_levels_internal(request=object(), repository=repository)

    assert calls["token"] == 1
    assert payload["status"] == "ok"
    assert payload["role_levels"] == {"admin": 99, "viewer": 0}


def test_get_isgl_meta_internal_reads_adhoc_and_display_name(monkeypatch):
    """Handle test get isgl meta internal reads adhoc and display name.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    calls = {"token": 0}

    monkeypatch.setattr(
        internal, "_require_internal_token", lambda _request: calls.__setitem__("token", 1)
    )
    monkeypatch.setattr(
        internal.util,
        "common",
        SimpleNamespace(convert_to_serializable=lambda payload: payload),
        raising=False,
    )
    repository = SimpleNamespace(
        is_isgl_adhoc=lambda _isgl_id: True,
        get_isgl_display_name=lambda _isgl_id: "Focus Panel",
    )

    payload = internal.get_isgl_meta_internal("ISGL123", request=object(), repository=repository)

    assert calls["token"] == 1
    assert payload == {
        "status": "ok",
        "isgl_id": "ISGL123",
        "is_adhoc": True,
        "display_name": "Focus Panel",
    }
