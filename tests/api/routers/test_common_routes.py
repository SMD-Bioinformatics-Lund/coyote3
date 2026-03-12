"""Behavior tests for Common API routes using collection-shaped fixtures."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routers import common
from api.repositories.common_repository import CommonRepository
from tests.fixtures.api import mock_collections as fx


def test_common_gene_info_read_by_symbol(monkeypatch):
    repository = CommonRepository()
    monkeypatch.setattr(repository, "get_hgnc_metadata_by_symbol", lambda symbol: {"symbol": symbol})
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = common.common_gene_info_read("TP53", repository=repository)
    assert payload["gene"]["symbol"] == "TP53"


def test_common_tiered_variant_context_not_found_raises_404(monkeypatch):
    repository = CommonRepository()
    monkeypatch.setattr(repository, "get_variant", lambda variant_id: None)

    with pytest.raises(HTTPException) as exc:
        common.common_tiered_variant_context_read("missing", 2, user=fx.api_user(), repository=repository)

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Variant not found"


def test_common_tiered_variant_context_insufficient_identity_returns_error_payload(monkeypatch):
    variant = {"_id": "v1", "INFO": {"selected_CSQ": {}}, "simple_id": None, "simple_id_hash": None}
    repository = CommonRepository()
    monkeypatch.setattr(repository, "get_variant", lambda variant_id: variant)
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = common.common_tiered_variant_context_read("v1", 3, user=fx.api_user(), repository=repository)
    assert payload["docs"] == []
    assert payload["tier"] == 3
    assert payload["error"] == "Variant has insufficient identity fields"
