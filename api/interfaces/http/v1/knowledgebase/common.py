"""Canonical common router module."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from api.app.container import util
from api.app.deps.application import get_knowledgebase, get_public_application
from api.interfaces.http.tags import TAG_KNOWLEDGEBASE
from api.security.access import ApiUser, require_access
from coyote3.application.operations.knowledgebase import Knowledgebase
from coyote3.application.operations.public import PublicApplication
from coyote3.contracts.common import (
    CancerGeneCensusSummaryPayload,
    CommonGeneCohortPayload,
    CommonGeneInfoPayload,
    CommonTieredVariantContextPayload,
    CommonTieredVariantSearchPayload,
    KnowledgebaseGenePayload,
    KnowledgebaseStatisticsPayload,
    KnowledgebaseVariantPayload,
)

router = APIRouter(tags=[TAG_KNOWLEDGEBASE])


@router.get("/api/v1/common/gene/{gene_id}/info", response_model=CommonGeneInfoPayload)
def common_gene_info_read(
    gene_id: str,
    service: PublicApplication = Depends(get_public_application),
):
    """Return metadata for a gene identifier or HGNC symbol."""
    return util.common.convert_to_serializable(service.gene_info(gene_id=gene_id))


@router.get(
    "/api/v1/common/gene/{gene_id}/cohort-summary",
    response_model=CommonGeneCohortPayload,
    summary="Get access-scoped cohort statistics for a tiered gene",
)
def common_gene_cohort_read(
    gene_id: str,
    include_history: Annotated[
        bool,
        Query(
            description=(
                "Include findings from all saved report versions. Repeated occurrences of "
                "the same typed finding in the same sample are counted once."
            )
        ),
    ] = False,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return prevalence and recurrent typed findings for visible samples."""
    return util.common.convert_to_serializable(
        service.gene_cohort(gene_id=gene_id, include_history=include_history)
    )


@router.get(
    "/api/v1/knowledgebases/cosmic/cancer-gene-census/summary",
    response_model=CancerGeneCensusSummaryPayload,
    summary="Get aggregate Cancer Gene Census information",
)
def cancer_gene_census_summary_read(
    user: ApiUser = Depends(require_access()),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return non-clinical CGC distributions when the collection is populated."""
    return util.common.convert_to_serializable(service.cancer_gene_census_summary())


@router.get(
    "/api/v1/knowledgebases/statistics",
    response_model=KnowledgebaseStatisticsPayload,
    summary="Get aggregate knowledgebase statistics",
)
def knowledgebase_statistics_read(
    user: ApiUser = Depends(require_access()),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return non-clinical source coverage statistics."""
    return util.common.convert_to_serializable(service.statistics())


@router.get(
    "/api/v1/knowledgebases/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get aggregated external knowledgebase context for a gene",
)
def knowledgebase_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return HGNC-normalized gene context across configured knowledgebases."""
    return util.common.convert_to_serializable(service.gene(gene_id=gene_id))


@router.get(
    "/api/v1/knowledgebases/oncokb/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get OncoKB gene context from local public and historical caches",
)
def knowledgebase_oncokb_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return only OncoKB-related gene context."""
    return util.common.convert_to_serializable(service.oncokb_gene(gene_id=gene_id))


@router.get(
    "/api/v1/knowledgebases/clinpgx/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get ClinPGx public gene marker context",
)
def knowledgebase_clinpgx_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return only local ClinPGx public gene-marker context."""
    return util.common.convert_to_serializable(service.clinpgx_gene(gene_id=gene_id))


@router.get(
    "/api/v1/knowledgebases/civic/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get CIViC gene context",
)
def knowledgebase_civic_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return only local CIViC gene context."""
    return util.common.convert_to_serializable(service.civic_gene(gene_id=gene_id))


@router.get(
    "/api/v1/knowledgebases/brca-exchange/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get BRCA Exchange applicability for a gene",
)
def knowledgebase_brca_exchange_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return BRCA Exchange gene applicability context."""
    return util.common.convert_to_serializable(service.brca_exchange_gene(gene_id=gene_id))


@router.get(
    "/api/v1/knowledgebases/iarc-tp53/gene/{gene_id}",
    response_model=KnowledgebaseGenePayload,
    summary="Get IARC TP53 applicability for a gene",
)
def knowledgebase_iarc_tp53_gene_read(
    gene_id: str,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return IARC TP53 gene applicability context."""
    return util.common.convert_to_serializable(service.iarc_tp53_gene(gene_id=gene_id))


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
    genome_build: int | None = None,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return local CIViC, OncoKB, BRCA Exchange, and IARC TP53 context."""
    return util.common.convert_to_serializable(
        service.variant_evidence(
            chrom=chrom,
            pos=pos,
            ref=ref,
            alt=alt,
            gene=gene,
            hgvsc=hgvsc,
            hgvsp=hgvsp,
            assay_group=assay_group,
            genome_build=genome_build,
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
    genome_build: int | None = None,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return local CIViC variant evidence for one variant identity."""
    return util.common.convert_to_serializable(
        service.civic_variant_evidence(
            chrom=chrom,
            pos=pos,
            ref=ref,
            alt=alt,
            gene=gene,
            hgvsc=hgvsc,
            hgvsp=hgvsp,
            assay_group=assay_group,
            genome_build=genome_build,
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
    genome_build: int | None = None,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return local BRCA Exchange variant evidence for one variant identity."""
    return util.common.convert_to_serializable(
        service.brca_exchange_variant_evidence(
            chrom=chrom,
            pos=pos,
            ref=ref,
            alt=alt,
            gene=gene,
            hgvsc=hgvsc,
            hgvsp=hgvsp,
            assay_group=assay_group,
            genome_build=genome_build,
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
    genome_build: int | None = None,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return local IARC TP53 variant evidence for one variant identity."""
    return util.common.convert_to_serializable(
        service.iarc_tp53_variant_evidence(
            chrom=chrom,
            pos=pos,
            ref=ref,
            alt=alt,
            gene=gene,
            hgvsc=hgvsc,
            hgvsp=hgvsp,
            assay_group=assay_group,
            genome_build=genome_build,
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
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Return reported-variant context restricted to the caller's visible samples."""

    return util.common.convert_to_serializable(
        service.tiered_variant_context(variant_id=variant_id, tier=tier)
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
    nomenclatures: list[str] | None = Query(default=None),
    limit_entries: int | None = None,
    user: ApiUser = Depends(require_access(permission="gene.annotation:view")),
    service: Knowledgebase = Depends(get_knowledgebase),
):
    """Search tiered variants and related annotations across reports."""
    return util.common.convert_to_serializable(
        service.tiered_variant_search(
            search_str=search_str,
            search_mode=search_mode,
            include_annotation_text=include_annotation_text,
            assays=assays,
            assay=assay,
            nomenclatures=nomenclatures,
            limit_entries=limit_entries,
        )
    )
