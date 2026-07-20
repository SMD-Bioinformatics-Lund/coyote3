"""Canonical common router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.app.container import util
from api.app.deps.services import get_common_query_service
from api.app.runtime_state import app as runtime_app
from api.application.common.query_service import CommonQueryService
from api.contracts.common import (
    CommonGeneInfoPayload,
    CommonTieredVariantContextPayload,
    CommonTieredVariantSearchPayload,
    KnowledgebaseGenePayload,
    KnowledgebaseVariantPayload,
)
from api.interfaces.http.tags import TAG_KNOWLEDGEBASE
from api.security.access import ApiUser, require_access

router = APIRouter(tags=[TAG_KNOWLEDGEBASE])


def _single_source_gene_payload(
    *, service: CommonQueryService, gene_id: str, source_keys: tuple[str, ...]
) -> dict:
    """Return a gene payload narrowed to one knowledgebase family."""
    payload = service.knowledgebase_gene_payload(gene_id)
    sources = {key: payload["sources"].get(key) for key in source_keys}
    payload["sources"] = sources
    payload["available_sources"] = service._available_sources(sources)
    return payload


def _single_source_variant_payload(
    *,
    service: CommonQueryService,
    source_keys: tuple[str, ...],
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    gene: str,
    hgvsc: str | None,
    hgvsp: str | None,
    assay_group: str,
) -> dict:
    """Return a variant-evidence payload narrowed to one knowledgebase family."""
    payload = service.knowledgebase_variant_payload(
        chrom=chrom,
        pos=pos,
        ref=ref,
        alt=alt,
        gene=gene,
        hgvsc=hgvsc,
        hgvsp=hgvsp,
        assay_group=assay_group,
    )
    sources = {key: payload["sources"].get(key) for key in source_keys}
    payload["sources"] = sources
    payload["available_sources"] = service._available_sources(sources)
    return payload


@router.get("/api/v1/common/gene/{gene_id}/info", response_model=CommonGeneInfoPayload)
def common_gene_info_read(
    gene_id: str,
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return metadata for a gene identifier or HGNC symbol."""
    return util.common.convert_to_serializable(service.gene_info_payload(gene_id))


@router.get(
    "/api/v1/knowledgebases/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get aggregated external knowledgebase context for a gene",
)
def knowledgebase_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return HGNC-normalized gene context across configured knowledgebases."""
    _ = user
    return util.common.convert_to_serializable(service.knowledgebase_gene_payload(gene_id))


@router.get(
    "/api/v1/knowledgebases/oncokb/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get OncoKB gene context from local public and historical caches",
)
def knowledgebase_oncokb_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return only OncoKB-related gene context."""
    _ = user
    payload = service.knowledgebase_gene_payload(gene_id)
    sources = {key: value for key, value in payload["sources"].items() if key.startswith("oncokb")}
    payload["sources"] = sources
    payload["available_sources"] = service._available_sources(sources)
    return util.common.convert_to_serializable(payload)


@router.get(
    "/api/v1/knowledgebases/clinpgx/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get ClinPGx public gene marker context",
)
def knowledgebase_clinpgx_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return only local ClinPGx public gene-marker context."""
    _ = user
    payload = service.knowledgebase_gene_payload(gene_id)
    sources = {"clinpgx_public": payload["sources"].get("clinpgx_public")}
    payload["sources"] = sources
    payload["available_sources"] = service._available_sources(sources)
    return util.common.convert_to_serializable(payload)


@router.get(
    "/api/v1/knowledgebases/civic/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get CIViC gene context",
)
def knowledgebase_civic_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return only local CIViC gene context."""
    _ = user
    payload = service.knowledgebase_gene_payload(gene_id)
    sources = {"civic_gene": payload["sources"].get("civic_gene")}
    payload["sources"] = sources
    payload["available_sources"] = service._available_sources(sources)
    return util.common.convert_to_serializable(payload)


@router.get(
    "/api/v1/knowledgebases/brca-exchange/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get BRCA Exchange applicability for a gene",
)
def knowledgebase_brca_exchange_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return BRCA Exchange gene applicability context."""
    _ = user
    return util.common.convert_to_serializable(
        _single_source_gene_payload(
            service=service,
            gene_id=gene_id,
            source_keys=("brca_exchange",),
        )
    )


@router.get(
    "/api/v1/knowledgebases/iarc-tp53/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get IARC TP53 applicability for a gene",
)
def knowledgebase_iarc_tp53_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return IARC TP53 gene applicability context."""
    _ = user
    return util.common.convert_to_serializable(
        _single_source_gene_payload(
            service=service,
            gene_id=gene_id,
            source_keys=("iarc_tp53",),
        )
    )


@router.get(
    "/api/v1/knowledgebases/variant/evidence",
    response_model=KnowledgebaseVariantPayload,
    summary="Get local external-database evidence for one variant",
)
def knowledgebase_variant_evidence_read(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    gene: str,
    hgvsc: str | None = None,
    hgvsp: str | None = None,
    assay_group: str = "dna",
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return local CIViC, OncoKB, BRCA Exchange, and IARC TP53 context."""
    _ = user
    return util.common.convert_to_serializable(
        service.knowledgebase_variant_payload(
            chrom=chrom,
            pos=pos,
            ref=ref,
            alt=alt,
            gene=gene,
            hgvsc=hgvsc,
            hgvsp=hgvsp,
            assay_group=assay_group,
        )
    )


@router.get(
    "/api/v1/knowledgebases/civic/variant/evidence",
    response_model=KnowledgebaseVariantPayload,
    summary="Get CIViC evidence for one variant",
)
def knowledgebase_civic_variant_evidence_read(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    gene: str,
    hgvsc: str | None = None,
    hgvsp: str | None = None,
    assay_group: str = "dna",
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return local CIViC variant evidence for one variant identity."""
    _ = user
    return util.common.convert_to_serializable(
        _single_source_variant_payload(
            service=service,
            source_keys=("civic_variants",),
            chrom=chrom,
            pos=pos,
            ref=ref,
            alt=alt,
            gene=gene,
            hgvsc=hgvsc,
            hgvsp=hgvsp,
            assay_group=assay_group,
        )
    )


@router.get(
    "/api/v1/knowledgebases/brca-exchange/variant/evidence",
    response_model=KnowledgebaseVariantPayload,
    summary="Get BRCA Exchange evidence for one variant",
)
def knowledgebase_brca_exchange_variant_evidence_read(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    gene: str,
    hgvsc: str | None = None,
    hgvsp: str | None = None,
    assay_group: str = "dna",
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return local BRCA Exchange variant evidence for one variant identity."""
    _ = user
    return util.common.convert_to_serializable(
        _single_source_variant_payload(
            service=service,
            source_keys=("brca_exchange",),
            chrom=chrom,
            pos=pos,
            ref=ref,
            alt=alt,
            gene=gene,
            hgvsc=hgvsc,
            hgvsp=hgvsp,
            assay_group=assay_group,
        )
    )


@router.get(
    "/api/v1/knowledgebases/iarc-tp53/variant/evidence",
    response_model=KnowledgebaseVariantPayload,
    summary="Get IARC TP53 evidence for one variant",
)
def knowledgebase_iarc_tp53_variant_evidence_read(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    gene: str,
    hgvsc: str | None = None,
    hgvsp: str | None = None,
    assay_group: str = "dna",
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return local IARC TP53 variant evidence for one variant identity."""
    _ = user
    return util.common.convert_to_serializable(
        _single_source_variant_payload(
            service=service,
            source_keys=("iarc_tp53",),
            chrom=chrom,
            pos=pos,
            ref=ref,
            alt=alt,
            gene=gene,
            hgvsc=hgvsc,
            hgvsp=hgvsp,
            assay_group=assay_group,
        )
    )


@router.get(
    "/api/v1/common/reported_variants/variant/{variant_id}/{tier}",
    response_model=CommonTieredVariantContextPayload,
)
def common_tiered_variant_context_read(
    variant_id: str,
    tier: int,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return reported-variant context for a specific tiered variant."""
    _ = user
    return util.common.convert_to_serializable(
        service.tiered_variant_context_payload(variant_id=variant_id, tier=tier)
    )


@router.get(
    "/api/v1/common/search/tiered_variants", response_model=CommonTieredVariantSearchPayload
)
def common_tiered_variant_search_read(
    search_str: str | None = None,
    search_mode: str = "gene",
    include_annotation_text: bool = False,
    assays: list[str] | None = Query(default=None),
    assay: list[str] | None = Query(default=None),
    limit_entries: int | None = None,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Search tiered variants and related annotations across reports."""
    _ = user
    if limit_entries is None:
        limit_entries = runtime_app.config.get("TIERED_VARIANT_SEARCH_LIMIT", 1000)
    selected_assays = assays or assay
    return util.common.convert_to_serializable(
        service.tiered_variant_search_payload(
            search_str=search_str,
            search_mode=search_mode,
            include_annotation_text=include_annotation_text,
            assays=selected_assays,
            limit_entries=limit_entries,
        )
    )
