"""Behavior tests for Admin API routes using collection-shaped fixtures."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.interfaces.http.v1.admin import roles
from coyote3.application.operations import administration as sdk_administration
from tests.fixtures.api import application_sdk as sdk_fixtures
from tests.fixtures.api import mock_collections as fx


def test_list_roles_read_success(monkeypatch):
    monkeypatch.setattr(roles.util.common, "convert_to_serializable", lambda payload: payload)

    service = type(
        "_Service",
        (),
        {"list_roles_payload": staticmethod(lambda **_: {"roles": [fx.role_doc()]})},
    )()
    payload = sdk_fixtures.invoke_route(
        roles.list_roles_read,
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_administration.Roles, service, fx.api_user()
        ),
    )
    assert payload["roles"][0]["_id"] == fx.role_doc()["_id"]


def test_create_role_context_read_no_schema_raises_400(monkeypatch):
    service = type(
        "_Service",
        (),
        {
            "create_context_payload": staticmethod(
                lambda **kwargs: (_ for _ in ()).throw(
                    HTTPException(status_code=400, detail={"error": "No active role schemas found"})
                )
            )
        },
    )()

    with pytest.raises(HTTPException) as exc:
        sdk_fixtures.invoke_route(
            roles.create_role_context_read,
            user=fx.api_user(),
            service=sdk_fixtures.authorized_operations(
                sdk_administration.Roles, service, fx.api_user()
            ),
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "No active role schemas found"


def test_role_context_read_not_found_raises_404(monkeypatch):
    service = type(
        "_Service",
        (),
        {
            "context_payload": staticmethod(
                lambda **kwargs: (_ for _ in ()).throw(
                    HTTPException(status_code=404, detail={"error": "Role not found"})
                )
            )
        },
    )()

    with pytest.raises(HTTPException) as exc:
        sdk_fixtures.invoke_route(
            roles.role_context_read,
            "missing",
            user=fx.api_user(),
            service=sdk_fixtures.authorized_operations(
                sdk_administration.Roles, service, fx.api_user()
            ),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Role not found"
