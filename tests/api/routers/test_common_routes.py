"""Behavior tests for Common API routes using collection-shaped fixtures."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.repositories.common_repository import CommonRepository
from api.routers import common
from tests.fixtures.api import mock_collections as fx


def test_common_gene_info_read_by_symbol(monkeypatch):
    """Test common gene info read by symbol.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    repository = CommonRepository()
    monkeypatch.setattr(
        repository, "get_hgnc_metadata_by_symbol", lambda symbol: {"symbol": symbol}
    )
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = common.common_gene_info_read("TP53", repository=repository)
    assert payload["gene"]["symbol"] == "TP53"


def test_common_tiered_variant_context_not_found_raises_404(monkeypatch):
    """Test common tiered variant context not found raises 404.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    repository = CommonRepository()
    monkeypatch.setattr(repository, "get_variant", lambda variant_id: None)

    with pytest.raises(HTTPException) as exc:
        common.common_tiered_variant_context_read(
            "missing", 2, user=fx.api_user(), repository=repository
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Variant not found"


def test_common_tiered_variant_context_insufficient_identity_returns_error_payload(monkeypatch):
    """Test common tiered variant context insufficient identity returns error payload.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    variant = {"_id": "v1", "INFO": {"selected_CSQ": {}}, "simple_id": None, "simple_id_hash": None}
    repository = CommonRepository()
    monkeypatch.setattr(repository, "get_variant", lambda variant_id: variant)
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = common.common_tiered_variant_context_read(
        "v1", 3, user=fx.api_user(), repository=repository
    )
    assert payload["docs"] == []
    assert payload["tier"] == 3
    assert payload["error"] == "Variant has insufficient identity fields"


def test_common_tiered_variant_context_uses_hash_and_simple_id(monkeypatch):
    """Exact identity lookup must prefilter by hash and verify by simple_id."""
    variant = {
        "_id": "v1",
        "simple_id": " chr17_7579472_c_t ",
        "simple_id_hash": None,
        "INFO": {"selected_CSQ": {"SYMBOL": "TP53"}},
    }
    captured: dict = {}
    repository = CommonRepository()
    monkeypatch.setattr(repository, "get_variant", lambda variant_id: variant)
    monkeypatch.setattr(
        repository,
        "list_reported_variants",
        lambda query: captured.setdefault("query", query) or [],
    )
    monkeypatch.setattr(common, "enrich_reported_variant_docs", lambda docs: docs)
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = common.common_tiered_variant_context_read(
        "v1", 2, user=fx.api_user(), repository=repository
    )

    assert payload["error"] is None
    assert captured["query"] == {
        "gene": "TP53",
        "$or": [
            {
                "$and": [
                    {"simple_id_hash": "862b46287a08e369aa99f8f3777f44b9"},
                    {"simple_id": "17_7579472_C_T"},
                ]
            }
        ],
    }
