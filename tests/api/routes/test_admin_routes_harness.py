"""Integration-style admin route tests using shared fake-store harness."""

from __future__ import annotations

from api.routes import admin
from tests.api.fixtures import mock_collections as fx
from tests.api.fixtures.fake_store import build_fake_store


def test_list_roles_read_with_fake_store(monkeypatch):
    fake_store = build_fake_store()
    monkeypatch.setattr(admin, "store", fake_store)
    monkeypatch.setattr(admin.util.common, "convert_to_serializable", lambda payload: payload)

    payload = admin.list_roles_read(user=fx.api_user())

    assert payload["roles"][0]["_id"] == fx.role_doc()["_id"]
    assert payload["roles"][0]["level"] == int(fx.role_doc().get("level") or 0)


def test_create_role_context_read_with_fake_store(monkeypatch):
    fake_store = build_fake_store()
    monkeypatch.setattr(admin, "store", fake_store)
    monkeypatch.setattr(admin.util.common, "utc_now", lambda: "NOW")
    monkeypatch.setattr(admin.util.common, "convert_to_serializable", lambda payload: payload)

    expected_schema_id = fx.schema_doc()["_id"]
    payload = admin.create_role_context_read(schema_id=expected_schema_id, user=fx.api_user())

    assert payload["selected_schema"]["_id"] == expected_schema_id
    assert payload["schema"]["fields"]["created_by"]["default"] == "tester"
