"""Canonical public router module."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query, Response

from api.app.container import util
from api.app.deps.application import get_public_application, get_public_pages
from api.contracts.public_pages import PublicAboutPayload, PublicContactPayload
from api.interfaces.http.tags import TAG_PUBLIC
from api.services.public_pages import PublicPages
from coyote3.application.operations.public import PublicApplication
from coyote3.contracts.public import (
    PublicAspGenesPayload,
    PublicAssayCatalogGenesCsvPayload,
    PublicAssayCatalogMatrixPayload,
    PublicAssayCatalogPayload,
    PublicFilterFlagMetadataPayload,
    PublicGenelistViewPayload,
    PublicGeneSymbolsPayload,
    PublicKnowledgebaseStatusPayload,
    PublicModulesPayload,
    PublicVepReferencePayload,
    PublicVepVersionsPayload,
)
from coyote3.contracts.schemas.catalog_offerings import CatalogDiscoveryDoc

router = APIRouter(tags=[TAG_PUBLIC])
__all__ = ["router"]


@router.get("/api/v1/public/vep", response_model=PublicVepVersionsPayload)
def public_vep_versions_read(service: PublicApplication = Depends(get_public_application)):
    """List installed VEP reference releases. Public access; no sample data is returned."""
    return util.common.convert_to_serializable(service.vep_versions())


@router.get("/api/v1/public/vep/{release}", response_model=PublicVepReferencePayload)
def public_vep_reference_read(
    release: str, service: PublicApplication = Depends(get_public_application)
):
    """Read consequence definitions and diagram for an exact installed VEP release.

    Public access. An unavailable release returns 404 rather than newer metadata.

    Args:
        release: Installed major Ensembl release identifier.

    Returns:
        Reference tables, groups, source links and an optional locally stored diagram.
    """
    return util.common.convert_to_serializable(service.vep_reference(release=release))


@router.get("/api/v1/public/vep/{release}/diagram", response_class=Response)
def public_vep_diagram_read(
    release: str, service: PublicApplication = Depends(get_public_application)
):
    """Return the locally installed Ensembl diagram. Public, read-only access.

    Args:
        release: Exact installed major Ensembl release.

    Returns:
        Image bytes with their MIME type and content digest; 404 if absent.
    """
    diagram = service.vep_diagram(release=release)
    return Response(
        content=bytes(diagram["data"]),
        media_type=diagram["mime_type"],
        headers={
            "ETag": f'"{diagram["_id"]}"',
            "Cache-Control": "public, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:; sandbox",
        },
    )


@router.get("/api/v1/public/contact", response_model=PublicContactPayload)
def public_contact_read(service: PublicPages = Depends(get_public_pages)):
    """Return center-owned public contact and support metadata."""
    return util.common.convert_to_serializable(service.contact())


@router.get("/api/v1/public/modules", response_model=PublicModulesPayload)
def public_modules_read(service: PublicApplication = Depends(get_public_application)):
    """Return effective availability for software-defined application modules."""
    return util.common.convert_to_serializable(service.modules())


@router.get("/api/v1/public/about", response_model=PublicAboutPayload)
def public_about_read(service: PublicPages = Depends(get_public_pages)):
    """Return public application, support, and reference-version metadata."""
    return util.common.convert_to_serializable(service.about())


@router.get(
    "/api/v1/public/knowledgebases/status",
    response_model=PublicKnowledgebaseStatusPayload,
)
def public_knowledgebase_status_read(
    service: PublicApplication = Depends(get_public_application),
) -> dict[str, Any]:
    """Return installed knowledgebase products, releases, and record counts."""
    return util.common.convert_to_serializable(service.knowledgebase_status())


@router.get("/api/v1/public/filter-flags/metadata", response_model=PublicFilterFlagMetadataPayload)
def public_filter_flag_metadata_read(service: PublicApplication = Depends(get_public_application)):
    """Return center-configurable VCF filter flag metadata."""
    return util.common.convert_to_serializable(service.filter_flag_metadata())


@router.get(
    "/api/v1/public/genelists/{genelist_id}/view_context", response_model=PublicGenelistViewPayload
)
def public_genelist_view_context_read(
    genelist_id: str,
    assay: str | None = None,
    service: PublicApplication = Depends(get_public_application),
):
    """Return public view context for a genelist.

    \u000c

    Args:
        genelist_id: Genelist identifier to inspect.
        assay: Optional assay used to scope visible genes.

    Returns:
        dict: Public genelist view payload.
    """
    return util.common.convert_to_serializable(
        service.genelist_view_context(genelist_id=genelist_id, assay=assay)
    )


@router.get("/api/v1/public/asp/{asp_id}/genes", response_model=PublicAspGenesPayload)
def public_asp_genes_read(
    asp_id: str, service: PublicApplication = Depends(get_public_application)
):
    """Return public genes for an assay panel.

    \u000c

    Args:
        asp_id: Assay-panel identifier to inspect.

    Returns:
        dict: Public assay-panel gene payload.
    """
    return util.common.convert_to_serializable(service.asp_genes(asp_id=asp_id))


@router.get(
    "/api/v1/public/assay-catalog/genes/{isgl_key}/view_context",
    response_model=PublicGeneSymbolsPayload,
)
def public_assay_catalog_isgl_genes_view_read(
    isgl_key: str, service: PublicApplication = Depends(get_public_application)
):
    """Return public catalog genes for a catalog genelist.

    \u000c

    Args:
        isgl_key: Catalog genelist identifier to inspect.

    Returns:
        dict: Public gene-symbol payload.
    """
    return util.common.convert_to_serializable(
        service.assay_catalog_isgl_genes_view(isgl_key=isgl_key)
    )


@router.get(
    "/api/v1/public/assay-catalog-matrix/context", response_model=PublicAssayCatalogMatrixPayload
)
def public_assay_catalog_matrix_context_read(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=500),
    gene: str | None = None,
    service: PublicApplication = Depends(get_public_application),
):
    """Return the public assay-catalog matrix payload.

    Returns:
        dict: Assay-catalog matrix payload.
    """
    return util.common.convert_to_serializable(
        service.assay_catalog_matrix_context(page=page, per_page=per_page, gene=gene)
    )


@router.get("/api/v1/public/assay-catalog/offerings", response_model=CatalogDiscoveryDoc)
def public_catalog_offerings_read(service: PublicApplication = Depends(get_public_application)):
    """Browse reviewed service offerings, prices and effective gene scopes."""
    return util.common.convert_to_serializable(service.catalog_offerings())


@router.get("/api/v1/public/assay-catalog/context", response_model=PublicAssayCatalogPayload)
def public_assay_catalog_context_read(
    mod: str | None = None,
    cat: str | None = None,
    isgl_key: str | None = None,
    service: PublicApplication = Depends(get_public_application),
):
    """Return public assay-catalog context for the selected modality/category."""
    return util.common.convert_to_serializable(
        service.assay_catalog_context(mod=mod, cat=cat, isgl_key=isgl_key)
    )


@router.get(
    "/api/v1/public/assay-catalog/genes.csv/context",
    response_model=PublicAssayCatalogGenesCsvPayload,
)
def public_assay_catalog_genes_csv_context_read(
    mod: str,
    cat: str | None = None,
    isgl_key: str | None = None,
    service: PublicApplication = Depends(get_public_application),
):
    """Return a CSV export payload for public assay-catalog genes."""
    return util.common.convert_to_serializable(
        service.assay_catalog_genes_csv_context(mod=mod, cat=cat, isgl_key=isgl_key)
    )
