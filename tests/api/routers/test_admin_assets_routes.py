"""Behavior tests for admin assay/genelist/aspc/schema route handlers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from api.main import app as api_app

from api.routers import admin_resources as admin


def test_list_asp_read_returns_panels(monkeypatch):
    monkeypatch.setattr(admin.util.common, "convert_to_serializable", lambda payload: payload)
    service = type("_Service", (), {"list_payload": staticmethod(lambda: {"panels": [{"_id": "WGS"}]})})()

    from tests.fixtures.api import mock_collections as fx
    payload = admin.list_asp_read(user=fx.api_user(), service=service)

    assert payload["panels"][0]["_id"] == "WGS"


def test_create_genelist_context_missing_schema_raises_404():
    from tests.fixtures.api import mock_collections as fx
    service = type(
        "_Service",
        (),
        {
            "create_context_payload": staticmethod(
                lambda **kwargs: (_ for _ in ()).throw(HTTPException(status_code=404, detail={"error": "Genelist schema not found"}))
            )
        },
    )()

    with pytest.raises(HTTPException) as exc:
        admin.create_genelist_context_read(schema_id="MISSING", user=fx.api_user(), service=service)

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Genelist schema not found"


def test_schema_context_read_returns_schema_payload(monkeypatch):
    monkeypatch.setattr(admin.util.common, "convert_to_serializable", lambda payload: payload)
    service = type("_Service", (), {"context_payload": staticmethod(lambda **kwargs: {"schema": {"_id": kwargs["schema_id"]}})})()

    payload = admin.schema_context_read("USER-SCHEMA", service=service)

    assert payload["schema"]["_id"] == "USER-SCHEMA"


def test_restful_admin_resource_routes_are_registered():
    paths = {route.path for route in api_app.routes}
    assert "/api/v1/admin/asp" in paths
    assert "/api/v1/admin/asp/{assay_panel_id}" in paths
    assert "/api/v1/admin/asp/{assay_panel_id}/status" in paths
    assert "/api/v1/admin/genelists" in paths
    assert "/api/v1/admin/genelists/{genelist_id}" in paths
    assert "/api/v1/admin/genelists/{genelist_id}/status" in paths
    assert "/api/v1/admin/aspc" in paths
    assert "/api/v1/admin/aspc/{assay_id}" in paths
    assert "/api/v1/admin/aspc/{assay_id}/status" in paths
    assert "/api/v1/admin/schemas" in paths
    assert "/api/v1/admin/schemas/{schema_id}" in paths
    assert "/api/v1/admin/schemas/{schema_id}/status" in paths
