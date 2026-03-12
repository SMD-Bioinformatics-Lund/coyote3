"""Behavior tests for Public API routes using collection-shaped fixtures."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routers import public
from tests.fixtures.api import mock_collections as fx


def test_public_genelist_view_context_not_found_raises_404(monkeypatch):
    monkeypatch.setattr(public.PublicCatalogService, "genelist_view_context", lambda *_args, **_kwargs: None)

    with pytest.raises(HTTPException) as exc:
        public.public_genelist_view_context_read("missing")

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Genelist not found"


def test_public_asp_genes_read_success(monkeypatch):
    monkeypatch.setattr(
        public.PublicCatalogService,
        "asp_genes_payload",
        lambda asp_id: {
            "asp_id": asp_id,
            "gene_details": [{"symbol": "TP53"}],
            "germline_gene_symbols": ["BRCA1"],
        },
    )
    monkeypatch.setattr(public.util.common, "convert_to_serializable", lambda payload: payload)

    payload = public.public_asp_genes_read("WGS")
    assert payload["asp_id"] == "WGS"
    assert payload["gene_details"][0]["symbol"] == "TP53"
    assert payload["germline_gene_symbols"] == ["BRCA1"]


def test_public_assay_catalog_context_missing_catalog_raises_404(monkeypatch):
    monkeypatch.setattr(public.PublicCatalogService, "load_catalog", lambda: {})
    monkeypatch.setattr(public.PublicCatalogService, "modalities_order", lambda: [])

    with pytest.raises(HTTPException) as exc:
        public.public_assay_catalog_context_read()

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Catalog not found"
