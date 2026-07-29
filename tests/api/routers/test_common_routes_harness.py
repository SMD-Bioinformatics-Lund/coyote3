"""Integration-style common route tests using shared fake-store harness."""

from __future__ import annotations

from types import SimpleNamespace

from api.application.common.query_service import CommonQueryService
from api.interfaces.http.knowledgebase import common
from tests.fixtures.api import mock_collections as fx
from tests.fixtures.api.fake_store import build_fake_store


def test_common_gene_info_read_numeric_path_with_fake_store(monkeypatch):
    """Test common gene info read numeric path with fake store.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    fake_store = build_fake_store()
    service = CommonQueryService(
        hgnc_repository=SimpleNamespace(
            get_metadata_by_hgnc_id=lambda hgnc_id: (
                fake_store.hgnc_repository.get_metadata_by_hgnc_id(hgnc_id=hgnc_id)
            )
        ),
        oncokb_repository=SimpleNamespace(get_oncokb_gene=lambda gene: None),
        variant_repository=SimpleNamespace(),
        reported_variant_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(),
        annotation_repository=SimpleNamespace(),
        sample_repository=SimpleNamespace(),
    )
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = common.common_gene_info_read("1234", service=service)

    assert payload["gene"]["hgnc_id"] == "1234"


def test_common_gene_info_read_resolves_previous_symbol(monkeypatch):
    """Gene info should resolve approved HGNC records through previous symbols."""
    hgnc_doc = {
        "hgnc_id": "HGNC:1",
        "hgnc_symbol": "NEW1",
        "prev_symbol": ["OLD1"],
    }
    service = CommonQueryService(
        hgnc_repository=SimpleNamespace(
            get_metadata_by_symbol_or_alias=lambda symbol: hgnc_doc if symbol == "OLD1" else None
        ),
        oncokb_repository=SimpleNamespace(get_oncokb_gene=lambda gene: None),
        variant_repository=SimpleNamespace(),
        reported_variant_repository=SimpleNamespace(),
        assay_panel_repository=SimpleNamespace(),
        annotation_repository=SimpleNamespace(),
        sample_repository=SimpleNamespace(),
    )
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = common.common_gene_info_read("OLD1", service=service)

    assert payload["gene"]["hgnc_symbol"] == "NEW1"
    assert payload["query"] == {
        "input": "OLD1",
        "resolved_symbol": "NEW1",
        "symbol_changed": True,
    }


def test_common_tiered_variant_context_read_with_fake_store(monkeypatch):
    """Test common tiered variant context read with fake store.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    fake_store = build_fake_store()
    service = CommonQueryService(
        variant_repository=SimpleNamespace(
            get_variant=lambda variant_id: fake_store.variant_repository.get_variant(variant_id)
        ),
        reported_variant_repository=SimpleNamespace(
            list_reported_variants=lambda query: list(
                fake_store.reported_variant_repository.list_reported_variants(query) or []
            )
        ),
        hgnc_repository=SimpleNamespace(),
        oncokb_repository=SimpleNamespace(get_oncokb_gene=lambda gene: None),
        assay_panel_repository=SimpleNamespace(),
        annotation_repository=SimpleNamespace(),
        sample_repository=SimpleNamespace(),
    )
    monkeypatch.setattr(
        "api.application.common.query_service.enrich_reported_variant_docs", lambda docs, **_: docs
    )
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = common.common_tiered_variant_context_read(
        "v1",
        2,
        user=fx.api_user(),
        service=service,
    )

    assert payload["tier"] == 2
    assert payload["error"] is None
    assert isinstance(payload["docs"], list)
