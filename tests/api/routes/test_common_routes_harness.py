"""Integration-style common route tests using shared fake-store harness."""

from __future__ import annotations

from api.routes import common
from tests.api.fixtures import mock_collections as fx
from tests.api.fixtures.fake_store import build_fake_store


def test_common_gene_info_read_numeric_path_with_fake_store(monkeypatch):
    fake_store = build_fake_store()
    monkeypatch.setattr(common, "store", fake_store)
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = common.common_gene_info_read("1234")

    assert payload["gene"]["hgnc_id"] == "1234"


def test_common_tiered_variant_context_read_with_fake_store(monkeypatch):
    fake_store = build_fake_store()
    monkeypatch.setattr(common, "store", fake_store)
    monkeypatch.setattr(common, "enrich_reported_variant_docs", lambda docs: docs)
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)

    payload = common.common_tiered_variant_context_read("v1", 2, user=fx.api_user())

    assert payload["tier"] == 2
    assert payload["error"] is None
    assert isinstance(payload["docs"], list)
