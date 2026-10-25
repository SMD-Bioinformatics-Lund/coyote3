"""Behavior tests for split admin assay/genelist/aspc route handlers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.routing import iter_route_contexts

from api.app.main import app as api_app
from api.interfaces.http.v1.admin.resources import asp, genelists
from coyote3.application.operations import administration as sdk_administration
from tests.fixtures.api import application_sdk as sdk_fixtures


def test_list_asp_read_returns_panels(monkeypatch):
    monkeypatch.setattr(asp.util.common, "convert_to_serializable", lambda payload: payload)
    service = type(
        "_Service",
        (),
        {"list_payload": staticmethod(lambda **_: {"panels": [{"_id": "WGS"}]})},
    )()

    from tests.fixtures.api import mock_collections as fx

    payload = sdk_fixtures.invoke_route(
        asp.list_asp_read,
        user=fx.api_user(),
        service=sdk_fixtures.authorized_operations(
            sdk_administration.Assays, service, fx.api_user()
        ),
    )

    assert payload["panels"][0]["_id"] == "WGS"


def test_create_genelist_context_surfaces_service_errors():
    from tests.fixtures.api import mock_collections as fx

    service = type(
        "_Service",
        (),
        {
            "create_context_payload": staticmethod(
                lambda **kwargs: (_ for _ in ()).throw(
                    HTTPException(status_code=404, detail={"error": "Genelist schema not found"})
                )
            )
        },
    )()

    with pytest.raises(HTTPException) as exc:
        sdk_fixtures.invoke_route(
            genelists.create_genelist_context_read,
            user=fx.api_user(),
            service=sdk_fixtures.authorized_operations(
                sdk_administration.GeneLists, service, fx.api_user()
            ),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Genelist schema not found"


def test_restful_admin_resource_routes_are_registered():
    paths = {route.path for route in iter_route_contexts(api_app.routes)}
    assert "/api/v1/resources/asp" in paths
    assert "/api/v1/resources/asp/{assay_panel_id}" in paths
    assert "/api/v1/resources/asp/{assay_panel_id}/fields/{field}" in paths
    assert "/api/v1/resources/asp/{assay_panel_id}/status" in paths
    assert "/api/v1/resources/assay-groups/{group_id}/fields/{field}" in paths
    assert "/api/v1/resources/diagnoses/{diagnosis_id}/fields/{field}" in paths
    assert "/api/v1/resources/genelists" in paths
    assert "/api/v1/resources/genelists/{genelist_id}" in paths
    assert "/api/v1/resources/genelists/{genelist_id}/fields/{field}" in paths
    assert "/api/v1/resources/genelists/{genelist_id}/status" in paths
    assert "/api/v1/resources/aspc" in paths
    assert "/api/v1/resources/aspc/{assay_id}" in paths
    assert "/api/v1/resources/aspc/{aspc_id}/fields/{field}" in paths
    assert "/api/v1/resources/aspc/{assay_id}/status" in paths
