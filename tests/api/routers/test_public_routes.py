"""Behavior tests for Public API routes using collection-shaped fixtures."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.app.deps import services
from api.app.runtime_state import app as runtime_app
from api.interfaces.http.v1.public import routes as public
from coyote3.application.public.catalog import PublicCatalogService
from coyote3.domain.exceptions import AppError
from tests.fixtures.api import application_sdk as sdk_fixtures


def test_public_genelist_view_context_not_found_raises_404(monkeypatch):
    monkeypatch.setattr(
        PublicCatalogService, "genelist_view_context", lambda self, *_args, **_kwargs: None
    )

    with pytest.raises(AppError) as exc:
        sdk_fixtures.invoke_route(
            public.public_genelist_view_context_read,
            "missing",
            service=sdk_fixtures.public_operations(),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Genelist not found"


def test_public_asp_genes_read_success(monkeypatch):
    monkeypatch.setattr(
        PublicCatalogService,
        "asp_genes_payload",
        lambda self, asp_id: {
            "asp_id": asp_id,
            "gene_details": [{"symbol": "TP53"}],
            "germline_gene_symbols": ["BRCA1"],
        },
    )
    monkeypatch.setattr(public.util.common, "convert_to_serializable", lambda payload: payload)

    payload = sdk_fixtures.invoke_route(
        public.public_asp_genes_read, "WGS", service=sdk_fixtures.public_operations()
    )
    assert payload["asp_id"] == "WGS"
    assert payload["gene_details"][0]["symbol"] == "TP53"
    assert payload["germline_gene_symbols"] == ["BRCA1"]


def test_public_contact_read_uses_runtime_config(monkeypatch):
    """Test public contact metadata is served from runtime configuration."""
    monkeypatch.setattr(
        runtime_app,
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

    payload = sdk_fixtures.invoke_route(
        public.public_contact_read, service=sdk_fixtures.public_pages()
    )

    assert payload["organization"]["name"] == "Center Genomics"
    assert payload["organization"]["department"] == "Molecular Pathology"
    assert payload["support"]["primary_email"] == "support@example.org"
    assert payload["contacts"][0]["label"] == "Clinical"


def test_public_assay_catalog_context_empty_installation_has_landing_page(monkeypatch):
    """An unconfigured installation keeps its landing page but rejects missing entries."""
    monkeypatch.setattr(PublicCatalogService, "_load_catalog_document", lambda self: {})
    assert (
        sdk_fixtures.invoke_route(
            public.public_assay_catalog_context_read, service=sdk_fixtures.public_operations()
        )["order"]
        == []
    )
    with pytest.raises(AppError) as exc:
        sdk_fixtures.invoke_route(
            public.public_assay_catalog_context_read,
            mod="dna",
            service=sdk_fixtures.public_operations(),
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Published offering not found"


def test_catalog_matrix_passes_pagination_and_gene_filter(monkeypatch):
    calls = {}

    def matrix(**kwargs):
        calls.update(kwargs)
        return {"genes": []}

    monkeypatch.setattr(
        services,
        "get_public_catalog_service",
        lambda: SimpleNamespace(published_matrix=matrix),
    )
    assert sdk_fixtures.invoke_route(
        public.public_assay_catalog_matrix_context_read,
        page=2,
        per_page=20,
        gene="TP53",
        service=sdk_fixtures.public_operations(),
    ) == {"genes": []}
    assert calls == {"page": 2, "per_page": 20, "gene": "TP53"}


@pytest.mark.parametrize("category", [None, "solid"])
def test_catalog_csv_exports_selected_genes(monkeypatch, category):
    service = SimpleNamespace(
        published_context=lambda *args: {
            "gene_mode": "published",
            "genes": [{"symbol": "TP53"}],
        },
    )
    monkeypatch.setattr(services, "get_public_catalog_service", lambda: service)
    payload = sdk_fixtures.invoke_route(
        public.public_assay_catalog_genes_csv_context_read,
        "wgs",
        cat=category,
        service=sdk_fixtures.public_operations(),
    )
    assert ",TP53," in payload["content"]
    assert payload["filename"].endswith(".genes.csv")


@pytest.mark.parametrize("category", [None, "missing"])
def test_catalog_csv_rejects_unknown_selection(monkeypatch, category):
    from coyote3.application.public.published_catalog_views import publication_context

    monkeypatch.setattr(
        services,
        "get_public_catalog_service",
        lambda: SimpleNamespace(
            published_context=lambda *args: publication_context(
                {"version": 0, "header": "Catalog", "description": "", "offerings": []}, *args
            ),
        ),
    )
    with pytest.raises(AppError) as exc:
        sdk_fixtures.invoke_route(
            public.public_assay_catalog_genes_csv_context_read,
            "wgs",
            cat=category,
            service=sdk_fixtures.public_operations(),
        )
    assert exc.value.status_code == 404
    assert exc.value.detail["error"] == "Published offering not found"
