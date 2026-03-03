"""Behavior tests for internal API routes."""

from __future__ import annotations

from api.routes import internal


def test_get_role_levels_internal_returns_id_to_level_map(monkeypatch):
    calls = {"token": 0}

    monkeypatch.setattr(internal, "_require_internal_token", lambda _request: calls.__setitem__("token", 1))
    monkeypatch.setattr(
        internal.store.roles_handler,
        "get_all_roles",
        lambda: [
            {"_id": "admin", "level": 99},
            {"_id": "viewer"},
        ],
    )
    monkeypatch.setattr(internal.util.common, "convert_to_serializable", lambda payload: payload)

    payload = internal.get_role_levels_internal(request=object())

    assert calls["token"] == 1
    assert payload["status"] == "ok"
    assert payload["role_levels"] == {"admin": 99, "viewer": 0}


def test_get_isgl_meta_internal_reads_adhoc_and_display_name(monkeypatch):
    calls = {"token": 0}

    monkeypatch.setattr(internal, "_require_internal_token", lambda _request: calls.__setitem__("token", 1))
    monkeypatch.setattr(internal.store.isgl_handler, "is_isgl_adhoc", lambda _isgl_id: True)
    monkeypatch.setattr(internal.store.isgl_handler, "get_isgl_display_name", lambda _isgl_id: "Focus Panel")
    monkeypatch.setattr(internal.util.common, "convert_to_serializable", lambda payload: payload)

    payload = internal.get_isgl_meta_internal("ISGL123", request=object())

    assert calls["token"] == 1
    assert payload == {
        "status": "ok",
        "isgl_id": "ISGL123",
        "is_adhoc": True,
        "display_name": "Focus Panel",
    }
