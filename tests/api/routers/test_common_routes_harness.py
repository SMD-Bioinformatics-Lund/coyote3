"""Integration-style common route tests using shared fake-store harness."""

from __future__ import annotations

from api.routers import common
from tests.fixtures.api import mock_collections as fx
from tests.fixtures.api.fake_store import build_fake_store


def test_common_gene_info_read_numeric_path_with_fake_store(monkeypatch):
    """Handle test common gene info read numeric path with fake store.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    fake_store = build_fake_store()
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)
    repository = type(
        "Repo",
        (),
        {
            "get_hgnc_metadata_by_id": lambda self, hgnc_id: fake_store.hgnc_handler.get_metadata_by_hgnc_id(
                hgnc_id=hgnc_id
            )
        },
    )()

    payload = common.common_gene_info_read("1234", repository=repository)

    assert payload["gene"]["hgnc_id"] == "1234"


def test_common_tiered_variant_context_read_with_fake_store(monkeypatch):
    """Handle test common tiered variant context read with fake store.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    fake_store = build_fake_store()
    monkeypatch.setattr(common, "enrich_reported_variant_docs", lambda docs: docs)
    monkeypatch.setattr(common.util.common, "convert_to_serializable", lambda payload: payload)
    repository = type(
        "Repo",
        (),
        {
            "get_variant": lambda self, variant_id: fake_store.variant_handler.get_variant(
                variant_id
            ),
            "list_reported_variants": lambda self, query: list(
                fake_store.reported_variants_handler.list_reported_variants(query) or []
            ),
        },
    )()

    payload = common.common_tiered_variant_context_read(
        "v1", 2, user=fx.api_user(), repository=repository
    )

    assert payload["tier"] == 2
    assert payload["error"] is None
    assert isinstance(payload["docs"], list)
