"""Canonical common router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from api.contracts.common import (
    CommonGeneInfoPayload,
    CommonTieredVariantContextPayload,
    CommonTieredVariantSearchPayload,
)
from api.deps.services import get_common_query_service
from api.extensions import util
from api.runtime_state import app as runtime_app
from api.security.access import ApiUser, require_access
from api.services.common.query_service import CommonQueryService

router = APIRouter(tags=["common"])


@router.get("/api/v1/common/gene/{gene_id}/info", response_model=CommonGeneInfoPayload)
def common_gene_info_read(
    gene_id: str,
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return metadata for a gene identifier or HGNC symbol."""
    return util.common.convert_to_serializable(service.gene_info_payload(gene_id))


@router.get(
    "/api/v1/common/reported_variants/variant/{variant_id}/{tier}",
    response_model=CommonTieredVariantContextPayload,
)
def common_tiered_variant_context_read(
    variant_id: str,
    tier: int,
    user: ApiUser = Depends(
        require_access(permission="gene.annotation:view", min_role="user", min_level=9)
    ),
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
    limit_entries: int | None = None,
    user: ApiUser = Depends(
        require_access(permission="gene.annotation:view", min_role="user", min_level=9)
    ),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Search tiered variants and related annotations across reports."""
    _ = user
    if limit_entries is None:
        limit_entries = runtime_app.config.get("TIERED_VARIANT_SEARCH_LIMIT", 1000)
    return util.common.convert_to_serializable(
        service.tiered_variant_search_payload(
            search_str=search_str,
            search_mode=search_mode,
            include_annotation_text=include_annotation_text,
            assays=assays,
            limit_entries=limit_entries,
        )
    )
