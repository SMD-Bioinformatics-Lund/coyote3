"""Behavior tests for split admin assay/genelist/aspc route handlers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.main import app as api_app
from api.routers.resources import asp, genelists


def test_list_asp_read_returns_panels(monkeypatch):
    """Test list asp read returns panels.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(asp.util.common, "convert_to_serializable", lambda payload: payload)
    service = type(
        "_Service",
        (),
        {"list_payload": staticmethod(lambda **_: {"panels": [{"_id": "WGS"}]})},
    )()

    from tests.fixtures.api import mock_collections as fx

    payload = asp.list_asp_read(user=fx.api_user(), service=service)

    assert payload["panels"][0]["_id"] == "WGS"


def test_create_genelist_context_missing_schema_raises_404():
    """Test create genelist context missing schema raises 404.

    Returns:
        The function result.
    """
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
        genelists.create_genelist_context_read(
            schema_id="MISSING", user=fx.api_user(), service=service
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Genelist schema not found"


def test_restful_admin_resource_routes_are_registered():
    """Test restful admin resource routes are registered.

    Returns:
        The function result.
    """
    paths = {route.path for route in api_app.routes}
    assert "/api/v1/resources/asp" in paths
    assert "/api/v1/resources/asp/{assay_panel_id}" in paths
    assert "/api/v1/resources/asp/{assay_panel_id}/status" in paths
    assert "/api/v1/resources/genelists" in paths
    assert "/api/v1/resources/genelists/{genelist_id}" in paths
    assert "/api/v1/resources/genelists/{genelist_id}/status" in paths
    assert "/api/v1/resources/aspc" in paths
    assert "/api/v1/resources/aspc/{assay_id}" in paths
    assert "/api/v1/resources/aspc/{assay_id}/status" in paths
