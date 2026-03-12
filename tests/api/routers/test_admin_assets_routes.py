"""Behavior tests for admin assay/genelist/aspc/schema route handlers."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routers import admin_resources as admin
from tests.api.fixtures import mock_collections as fx


def test_list_asp_read_returns_panels(monkeypatch):
    monkeypatch.setattr(admin.store.asp_handler, "get_all_asps", lambda: [{"_id": "WGS"}])
    monkeypatch.setattr(admin.util.common, "convert_to_serializable", lambda payload: payload)

    payload = admin.list_asp_read(user=fx.api_user())

    assert payload["panels"][0]["_id"] == "WGS"


def test_create_genelist_context_missing_schema_raises_404(monkeypatch):
    monkeypatch.setattr(
        admin.store.schema_handler,
        "get_schemas_by_category_type",
        lambda **kwargs: [{"_id": "SCHEMA_1", "fields": {}}],
    )

    with pytest.raises(HTTPException) as exc:
        admin.create_genelist_context_read(schema_id="MISSING", user=fx.api_user())

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Genelist schema not found"


def test_schema_context_read_returns_schema_payload(monkeypatch):
    monkeypatch.setattr(admin.store.schema_handler, "get_schema", lambda schema_id: {"_id": schema_id})
    monkeypatch.setattr(admin.util.common, "convert_to_serializable", lambda payload: payload)

    payload = admin.schema_context_read("USER-SCHEMA")

    assert payload["schema"]["_id"] == "USER-SCHEMA"
