"""Integration-style admin route tests using shared fake-store harness."""

from __future__ import annotations

from types import SimpleNamespace

from api.routers import roles
from tests.fixtures.api import mock_collections as fx
from tests.fixtures.api.fake_store import build_fake_store


def test_list_roles_read_with_fake_store(monkeypatch):
    fake_store = build_fake_store()
    monkeypatch.setattr(
        roles,
        "_admin_repo",
        lambda: SimpleNamespace(
            roles_handler=fake_store.roles_handler,
            permissions_handler=fake_store.permissions_handler,
            asp_handler=fake_store.asp_handler,
            schema_handler=fake_store.schema_handler,
            isgl_handler=fake_store.isgl_handler,
            sample_handler=fake_store.sample_handler,
        ),
    )
    monkeypatch.setattr(roles.util.common, "convert_to_serializable", lambda payload: payload)

    payload = roles.list_roles_read(user=fx.api_user())

    assert payload["roles"][0]["_id"] == fx.role_doc()["_id"]
    assert payload["roles"][0]["level"] == int(fx.role_doc().get("level") or 0)


def test_create_role_context_read_with_fake_store(monkeypatch):
    fake_store = build_fake_store()
    monkeypatch.setattr(
        roles,
        "_admin_repo",
        lambda: SimpleNamespace(
            roles_handler=fake_store.roles_handler,
            permissions_handler=fake_store.permissions_handler,
            asp_handler=fake_store.asp_handler,
            schema_handler=fake_store.schema_handler,
            isgl_handler=fake_store.isgl_handler,
            sample_handler=fake_store.sample_handler,
        ),
    )
    monkeypatch.setattr(roles.util.common, "utc_now", lambda: "NOW")
    monkeypatch.setattr(roles.util.common, "convert_to_serializable", lambda payload: payload)

    expected_schema_id = fx.schema_doc()["_id"]
    payload = roles.create_role_context_read(schema_id=expected_schema_id, user=fx.api_user())

    assert payload["selected_schema"]["_id"] == expected_schema_id
    assert payload["schema"]["fields"]["created_by"]["default"] == "tester"
