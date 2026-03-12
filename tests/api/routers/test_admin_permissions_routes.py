"""Behavior tests for Admin permission route handlers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routers import permissions
from tests.fixtures.api import mock_collections as fx


def test_list_permissions_read_groups_by_category(monkeypatch):
    permission = fx.permission_doc()
    monkeypatch.setattr(
        permissions._admin_repo().permissions_handler, "get_all_permissions", lambda is_active=False: [permission]
    )
    monkeypatch.setattr(permissions.util.common, "convert_to_serializable", lambda payload: payload)

    payload = permissions.list_permissions_read(user=fx.api_user())

    assert payload["permission_policies"][0]["_id"] == permission["_id"]
    assert "Uncategorized" not in payload["grouped_permissions"]
    assert permission["category"] in payload["grouped_permissions"]
    assert payload["permission_policies"][0]["is_active"] is True


def test_create_permission_context_read_no_schema_raises_400(monkeypatch):
    monkeypatch.setattr(
        permissions._admin_repo().schema_handler,
        "get_schemas_by_category_type",
        lambda **kwargs: [],
    )

    with pytest.raises(HTTPException) as exc:
        permissions.create_permission_context_read(user=fx.api_user())

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "No active permission schemas found"


def test_toggle_permission_mutation_sets_is_active_meta(monkeypatch):
    monkeypatch.setattr(
        permissions._admin_repo().permissions_handler,
        "get_permission",
        lambda perm_id: {"_id": perm_id, "is_active": False},
        raising=False,
    )
    monkeypatch.setattr(
        permissions._admin_repo().permissions_handler, "toggle_policy_active", lambda perm_id, status: None
    )
    monkeypatch.setattr(permissions.util.common, "convert_to_serializable", lambda payload: payload)

    payload = permissions.toggle_permission_mutation("perm.read", user=fx.api_user())

    assert payload["status"] == "ok"
    assert payload["action"] == "toggle"
    assert payload["meta"]["is_active"] is True


def test_toggle_permission_mutation_defaults_legacy_doc_to_active(monkeypatch):
    toggled: dict[str, bool] = {}

    monkeypatch.setattr(
        permissions._admin_repo().permissions_handler,
        "get_permission",
        lambda perm_id: {"_id": perm_id},
        raising=False,
    )
    monkeypatch.setattr(
        permissions._admin_repo().permissions_handler,
        "toggle_policy_active",
        lambda perm_id, status: toggled.setdefault(perm_id, status),
    )
    monkeypatch.setattr(permissions.util.common, "convert_to_serializable", lambda payload: payload)

    payload = permissions.toggle_permission_mutation("perm.legacy", user=fx.api_user())

    assert toggled["perm.legacy"] is False
    assert payload["meta"]["is_active"] is False
