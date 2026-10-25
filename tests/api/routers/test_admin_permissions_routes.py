"""Behavior tests for Admin permission route handlers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.interfaces.http.v1.admin import permissions
from coyote3.application.operations import administration as sdk_administration
from tests.fixtures.api import application_sdk as sdk_fixtures
from tests.fixtures.api import mock_collections as fx


def test_list_permissions_read_groups_by_category(monkeypatch):
    permission = fx.permission_doc()
    monkeypatch.setattr(permissions.util.common, "convert_to_serializable", lambda payload: payload)
    service = type(
        "_Service",
        (),
        {
            "list_permissions_payload": staticmethod(
                lambda **_: {
                    "permission_policies": [permission],
                    "grouped_permissions": {permission["category"]: [permission]},
                }
            )
        },
    )()

    payload = sdk_fixtures.invoke_route(
        permissions.list_permissions_read,
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_administration.Permissions, service, fx.api_user()
        ),
    )

    assert payload["permission_policies"][0]["_id"] == permission["_id"]
    assert "Uncategorized" not in payload["grouped_permissions"]
    assert permission["category"] in payload["grouped_permissions"]
    assert payload["permission_policies"][0]["is_active"] is True


def test_create_permission_context_read_no_schema_raises_400(monkeypatch):
    service = type(
        "_Service",
        (),
        {
            "create_context_payload": staticmethod(
                lambda **kwargs: (_ for _ in ()).throw(
                    HTTPException(
                        status_code=400, detail={"error": "No active permission schemas found"}
                    )
                )
            )
        },
    )()

    with pytest.raises(HTTPException) as exc:
        sdk_fixtures.invoke_route(
            permissions.create_permission_context_read,
            user=fx.api_user(),
            service=sdk_fixtures.authorized_operations(
                sdk_administration.Permissions, service, fx.api_user()
            ),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "No active permission schemas found"


def test_toggle_permission_status_sets_is_active_meta(monkeypatch):
    monkeypatch.setattr(permissions.util.common, "convert_to_serializable", lambda payload: payload)
    service = type(
        "_Service",
        (),
        {
            "toggle_permission": staticmethod(
                lambda **kwargs: {
                    "status": "ok",
                    "resource": "permission",
                    "resource_id": "perm.read",
                    "action": "toggle",
                    "sample_id": "admin",
                    "meta": {"is_active": True},
                }
            )
        },
    )()

    payload = sdk_fixtures.invoke_route(
        permissions.toggle_permission_status,
        "perm.read",
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_administration.Permissions, service, fx.api_user()
        ),
    )

    assert payload["status"] == "ok"
    assert payload["action"] == "toggle"
    assert payload["meta"]["is_active"] is True


def test_toggle_permission_status_defaults_historical_doc_to_active(monkeypatch):
    monkeypatch.setattr(permissions.util.common, "convert_to_serializable", lambda payload: payload)
    service = type(
        "_Service",
        (),
        {
            "toggle_permission": staticmethod(
                lambda **kwargs: {
                    "status": "ok",
                    "resource": "permission",
                    "resource_id": "perm.historical",
                    "action": "toggle",
                    "sample_id": "admin",
                    "meta": {"is_active": False},
                }
            )
        },
    )()

    payload = sdk_fixtures.invoke_route(
        permissions.toggle_permission_status,
        "perm.historical",
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_administration.Permissions, service, fx.api_user()
        ),
    )

    assert payload["meta"]["is_active"] is False
