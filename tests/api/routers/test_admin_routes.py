"""Behavior tests for Admin API routes using collection-shaped fixtures."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from types import SimpleNamespace

from api.routers import admin_resources
from api.routers import roles
from tests.fixtures.api import mock_collections as fx


def test_permission_policy_options_maps_permission_docs(monkeypatch):
    monkeypatch.setattr(admin_resources.store.permissions_handler, "get_all_permissions", lambda is_active=True: [fx.permission_doc()])
    options = admin_resources._permission_policy_options()
    expected = fx.permission_doc()
    assert options[0]["value"] == expected["_id"]
    assert options[0]["label"] == expected.get("label", expected["_id"])
    assert options[0]["category"] == expected.get("category", "Uncategorized")


def test_list_roles_read_success(monkeypatch):
    monkeypatch.setattr(
        roles,
        "_admin_repo",
        lambda: SimpleNamespace(roles_handler=SimpleNamespace(get_all_roles=lambda: [fx.role_doc()])),
    )
    monkeypatch.setattr(roles.util.common, "convert_to_serializable", lambda payload: payload)

    payload = roles.list_roles_read(user=fx.api_user())
    assert payload["roles"][0]["_id"] == fx.role_doc()["_id"]


def test_create_role_context_read_no_schema_raises_400(monkeypatch):
    monkeypatch.setattr(
        roles,
        "_admin_repo",
        lambda: SimpleNamespace(schema_handler=SimpleNamespace(get_schemas_by_category_type=lambda **kwargs: [])),
    )

    with pytest.raises(HTTPException) as exc:
        roles.create_role_context_read(user=fx.api_user())

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "No active role schemas found"


def test_role_context_read_not_found_raises_404(monkeypatch):
    monkeypatch.setattr(
        roles,
        "_admin_repo",
        lambda: SimpleNamespace(roles_handler=SimpleNamespace(get_role=lambda role_id: None)),
    )

    with pytest.raises(HTTPException) as exc:
        roles.role_context_read("missing", user=fx.api_user())

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Role not found"
