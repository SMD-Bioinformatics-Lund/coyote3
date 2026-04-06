"""Integration-style sample workflow route tests using shared fake-store harness."""

from __future__ import annotations

from types import SimpleNamespace

from api.routers import samples
from api.services.sample.catalog import SampleCatalogService
from tests.fixtures.api import mock_collections as fx
from tests.fixtures.api.fake_store import build_fake_store


def _catalog_service(fake_store) -> SampleCatalogService:
    return SampleCatalogService(
        sample_handler=fake_store.sample_handler,
        gene_list_handler=fake_store.gene_list_handler,
        assay_panel_handler=fake_store.assay_panel_handler,
        variant_handler=fake_store.variant_handler,
        grouped_coverage_handler=getattr(fake_store, "grouped_coverage_handler", SimpleNamespace()),
    )


def test_home_isgls_read_with_fake_store(monkeypatch):
    """Test home isgls read with fake store.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    fake_store = build_fake_store()
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)
    payload = samples.sample_genelists_read(
        "S1", user=fx.api_user(), service=_catalog_service(fake_store)
    )

    assert payload["items"][0]["isgl_id"] == str(fx.isgl_doc()["isgl_id"])
    assert payload["items"][0]["gene_count"] == int(fx.isgl_doc().get("gene_count") or 0)


def test_home_effective_genes_read_with_fake_store(monkeypatch):
    """Test home effective genes read with fake store.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    fake_store = build_fake_store()
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)
    payload = samples.sample_effective_genes_read(
        "S1", user=fx.api_user(), service=_catalog_service(fake_store)
    )

    assert "items" in payload
    assert payload["asp_covered_genes_count"] >= 1
