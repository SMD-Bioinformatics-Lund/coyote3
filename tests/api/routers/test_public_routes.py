"""Behavior tests for Public API routes using collection-shaped fixtures."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.domain.core.exceptions import AppError
from api.interfaces.http.public import routes as public


def test_public_genelist_view_context_not_found_raises_404(monkeypatch):
    """Test public genelist view context not found raises 404.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(
        public.PublicCatalogService, "genelist_view_context", lambda self, *_args, **_kwargs: None
    )

    with pytest.raises(AppError) as exc:
        public.public_genelist_view_context_read("missing")

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Genelist not found"


def test_public_asp_genes_read_success(monkeypatch):
    """Test public asp genes read success.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(
        public.PublicCatalogService,
        "asp_genes_payload",
        lambda self, asp_id: {
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


def test_public_contact_read_uses_runtime_config(monkeypatch):
    """Test public contact metadata is served from runtime configuration."""
    monkeypatch.setattr(
        public.runtime_app,
        "config",
        {
            "ORGANIZATION_NAME": "Center Genomics",
            "CONTACT": {
                "organization": {"department": "Molecular Pathology"},
                "support": {"primary_email": "support@example.org"},
                "contacts": [{"label": "Clinical", "email": "clinical@example.org"}],
                "links": [{"label": "Docs", "url": "/docs-site/"}],
                "hours": [{"label": "Office", "value": "08:00-16:00"}],
                "meta": {"source": "test"},
            },
        },
    )
    monkeypatch.setattr(public.util.common, "convert_to_serializable", lambda payload: payload)

    payload = public.public_contact_read()

    assert payload["organization"]["name"] == "Center Genomics"
    assert payload["organization"]["department"] == "Molecular Pathology"
    assert payload["support"]["primary_email"] == "support@example.org"
    assert payload["contacts"][0]["label"] == "Clinical"


def test_public_assay_catalog_context_missing_catalog_raises_404(monkeypatch):
    """Test public assay catalog context missing catalog raises 404.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(public.PublicCatalogService, "load_catalog", lambda self, **kwargs: {})

    with pytest.raises(AppError) as exc:
        public.public_assay_catalog_context_read()

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Catalog not found"


def test_catalog_matrix_passes_pagination_and_gene_filter(monkeypatch):
    calls = {}

    def matrix(**kwargs):
        calls.update(kwargs)
        return {"genes": []}

    monkeypatch.setattr(
        public,
        "get_public_catalog_service",
        lambda: SimpleNamespace(assay_catalog_matrix_payload=matrix),
    )
    assert public.public_assay_catalog_matrix_context_read(page=2, per_page=20, gene="TP53") == {
        "genes": []
    }
    assert calls == {"page": 2, "per_page": 20, "gene": "TP53"}


@pytest.mark.parametrize("category", [None, "solid"])
def test_catalog_csv_exports_selected_genes(monkeypatch, category):
    service = SimpleNamespace(
        normalize_mod=lambda mod: mod,
        hydrate_modality=lambda mod: {"asp_id": "panel"},
        hydrate_category=lambda *args, **kwargs: {"asp_id": "panel"},
        resolve_gene_table=lambda *args: (
            "asp",
            [{"hgnc_id": "HGNC:11998", "symbol": "TP53", "gene_type": ["protein-coding"]}],
            {},
        ),
    )
    monkeypatch.setattr(public, "get_public_catalog_service", lambda: service)
    payload = public.public_assay_catalog_genes_csv_context_read("wgs", cat=category)
    assert "HGNC:11998,TP53" in payload["content"]
    assert payload["filename"].endswith(".genes.csv")


@pytest.mark.parametrize(
    "valid_mod,category,error",
    [(False, None, "Modality not found"), (True, "missing", "Category not found")],
)
def test_catalog_csv_rejects_unknown_selection(monkeypatch, valid_mod, category, error):
    monkeypatch.setattr(
        public,
        "get_public_catalog_service",
        lambda: SimpleNamespace(
            normalize_mod=lambda mod: mod if valid_mod else None,
            hydrate_category=lambda *args, **kwargs: None,
        ),
    )
    with pytest.raises(AppError) as exc:
        public.public_assay_catalog_genes_csv_context_read("wgs", cat=category)
    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == error
