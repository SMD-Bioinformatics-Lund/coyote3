"""Repository contract tests for public catalog persistence adapters."""

from __future__ import annotations

from types import SimpleNamespace

from api.infra.repositories.public_catalog_mongo import PublicCatalogRepository


def test_public_catalog_repository_contract(monkeypatch):
    store_stub = SimpleNamespace(
        aspc_handler=SimpleNamespace(get_aspc_with_id=lambda aspc_id: {"aspc_id": aspc_id}),
        asp_handler=SimpleNamespace(
            get_asp=lambda asp_id: {"asp_id": asp_id},
            get_asp_genes=lambda asp_id: (["TP53", "EGFR"], ["BRCA1"]),
        ),
        isgl_handler=SimpleNamespace(
            get_isgl=lambda isgl_id, **kwargs: {"isgl_id": isgl_id, "filters": kwargs}
        ),
        hgnc_handler=SimpleNamespace(
            get_metadata_by_symbols=lambda symbols: [{"symbol": symbol} for symbol in symbols]
        ),
    )
    monkeypatch.setattr("api.infra.repositories.public_catalog_mongo.store", store_stub)

    repo = PublicCatalogRepository()

    assert repo.get_aspc_with_id("aspc1") == {"aspc_id": "aspc1"}
    assert repo.get_asp("asp1") == {"asp_id": "asp1"}
    assert repo.get_asp_genes("asp1") == (["TP53", "EGFR"], ["BRCA1"])
    assert repo.get_isgl(None) is None
    assert repo.get_isgl("gl1", is_active=True, is_public=False) == {
        "isgl_id": "gl1",
        "filters": {"is_active": True, "is_public": False},
    }
    assert repo.get_hgnc_metadata_by_symbols(["TP53", "EGFR"]) == [
        {"symbol": "TP53"},
        {"symbol": "EGFR"},
    ]
