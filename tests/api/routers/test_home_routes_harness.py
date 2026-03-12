"""Integration-style sample workflow route tests using shared fake-store harness."""

from __future__ import annotations

from api.routers import samples
from api.services.sample_catalog_service import SampleCatalogService
from tests.fixtures.api import mock_collections as fx
from tests.fixtures.api.fake_store import build_fake_store


def test_home_isgls_read_with_fake_store(monkeypatch):
    """Handle test home isgls read with fake store.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    fake_store = build_fake_store()
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)
    repository = type(
        "Repo",
        (),
        {
            "get_isgl_by_asp": lambda self, **query: list(fake_store.isgl_handler.get_isgl_by_asp(**query) or []),
        },
    )()

    payload = samples.sample_genelists_read("S1", user=fx.api_user(), service=SampleCatalogService(repository=repository))

    assert payload["items"][0]["_id"] == str(fx.isgl_doc()["_id"])
    assert payload["items"][0]["gene_count"] == int(fx.isgl_doc().get("gene_count") or 0)


def test_home_effective_genes_read_with_fake_store(monkeypatch):
    """Handle test home effective genes read with fake store.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    fake_store = build_fake_store()
    monkeypatch.setattr(samples, "_get_sample_for_api", lambda sample_id, user: fx.sample_doc())
    monkeypatch.setattr(samples.util.common, "convert_to_serializable", lambda payload: payload)
    repository = type(
        "Repo",
        (),
        {
            "get_asp": lambda self, assay: fake_store.asp_handler.get_asp(assay),
            "get_asp_genes": lambda self, assay: fake_store.asp_handler.get_asp_genes(assay),
            "get_isgl_by_ids": lambda self, ids: fake_store.isgl_handler.get_isgl_by_ids(ids),
        },
    )()

    payload = samples.sample_effective_genes_read("S1", user=fx.api_user(), service=SampleCatalogService(repository=repository))

    assert "items" in payload
    assert payload["asp_covered_genes_count"] >= 1
