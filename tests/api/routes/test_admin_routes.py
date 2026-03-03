"""Behavior tests for Admin API routes using collection-shaped fixtures."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routes import admin
from tests.api.fixtures import mock_collections as fx


def test_permission_policy_options_maps_permission_docs(monkeypatch):
    monkeypatch.setattr(admin.store.permissions_handler, "get_all_permissions", lambda is_active=True: [fx.permission_doc()])
    options = admin._permission_policy_options()
    assert options[0]["value"] == "view_role"
    assert options[0]["label"] == "View Role"
    assert options[0]["category"] == "RBAC"


def test_list_roles_read_success(monkeypatch):
    monkeypatch.setattr(admin.store.roles_handler, "get_all_roles", lambda: [fx.role_doc()])
    monkeypatch.setattr(admin.util.common, "convert_to_serializable", lambda payload: payload)

    payload = admin.list_roles_read(user=fx.api_user())
    assert payload["roles"][0]["_id"] == "admin"


def test_create_role_context_read_no_schema_raises_400(monkeypatch):
    monkeypatch.setattr(
        admin.store.schema_handler,
        "get_schemas_by_category_type",
        lambda **kwargs: [],
    )

    with pytest.raises(HTTPException) as exc:
        admin.create_role_context_read(user=fx.api_user())

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "No active role schemas found"


def test_role_context_read_not_found_raises_404(monkeypatch):
    monkeypatch.setattr(admin.store.roles_handler, "get_role", lambda role_id: None)

    with pytest.raises(HTTPException) as exc:
        admin.role_context_read("missing", user=fx.api_user())

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Role not found"
