"""Sample and coverage mutation router."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.home import (
    HomeChangeStatusPayload,
    HomeEditContextPayload,
    HomeEffectiveGenesPayload,
    HomeItemsPayload,
    HomeReportContextPayload,
    HomeSamplesPayload,
)
from api.contracts.samples import (
    CoverageBlacklistStatusPayload,
    CoverageBlacklistUpdateRequest,
    SampleChangePayload,
    SampleCommentCreateRequest,
    SampleFiltersUpdateRequest,
)
from api.core.rna.helpers import create_fusioncallers, create_fusioneffectlist
from api.core.workflows.filter_normalization import (
    normalize_dna_filter_keys,
    normalize_rna_filter_keys,
)
from api.deps.services import get_sample_catalog_service
from api.extensions import util
from api.http import api_error, get_formatted_assay_config
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.common.change_payload import change_payload
from api.services.interpretation.report_summary import create_comment_doc
from api.services.sample.catalog import SampleCatalogService

router = APIRouter(tags=["samples"])


@router.get("/api/v1/samples", response_model=HomeSamplesPayload)
def list_samples_read(
    status: str = "live",
    search_str: str = "",
    search_mode: str = "live",
    sample_view: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    live_page: int = Query(default=1, ge=1),
    done_page: int = Query(default=1, ge=1),
    live_per_page: int | None = Query(default=None, ge=1, le=200),
    done_per_page: int | None = Query(default=None, ge=1, le=200),
    profile_scope: str = Query(default="production"),
    panel_type: str | None = None,
    panel_tech: str | None = None,
    assay_group: str | None = None,
    limit_done_samples: int | None = None,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return the sample catalog for the current user."""
    _ = sample_view
    live_per_page = live_per_page or per_page
    done_per_page = done_per_page or per_page
    return util.common.convert_to_serializable(
        service.samples_payload(
            user=user,
            status=status,
            search_str=search_str,
            search_mode=search_mode,
            page=page,
            per_page=per_page,
            live_page=live_page,
            per_live_page=live_per_page,
            done_page=done_page,
            per_done_page=done_per_page,
            profile_scope=profile_scope,
            panel_type=panel_type,
            panel_tech=panel_tech,
            assay_group=assay_group,
            limit_done_samples=limit_done_samples,
        )
    )


@router.get("/api/v1/samples/{sample_id}/genelists", response_model=HomeItemsPayload)
def sample_genelists_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return selectable genelists for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.genelist_items_payload(sample=sample))


@router.get("/api/v1/samples/{sample_id}/effective-genes", response_model=HomeEffectiveGenesPayload)
def sample_effective_genes_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return the effective genes for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.effective_genes_payload(sample=sample))


@router.get("/api/v1/samples/{sample_id}/edit-context", response_model=HomeEditContextPayload)
def sample_edit_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return edit context for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(service.edit_context_payload(sample=sample))


@router.put(
    "/api/v1/samples/{sample_id}/genelists/selection", response_model=HomeChangeStatusPayload
)
def sample_apply_genelists_change(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Persist selected genelists for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.apply_genelists(sample=sample, payload=payload, sample_id=sample_id)
    )


@router.put("/api/v1/samples/{sample_id}/adhoc-genes", response_model=HomeChangeStatusPayload)
def sample_save_adhoc_genes_change(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Persist ad hoc genes for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.save_adhoc_genes(sample=sample, payload=payload, sample_id=sample_id)
    )


@router.delete("/api/v1/samples/{sample_id}/adhoc-genes", response_model=HomeChangeStatusPayload)
def sample_clear_adhoc_genes_change(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Clear ad hoc genes for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.clear_adhoc_genes(sample=sample, sample_id=sample_id)
    )


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_id}/context",
    response_model=HomeReportContextPayload,
)
def sample_report_context_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="view_reports", min_role="admin")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return report-download context for a sample report."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.report_context_payload(sample=sample, report_id=report_id, sample_id=sample_id)
    )


def _add_sample_comment(
    sample_id: str,
    payload: SampleCommentCreateRequest,
    user: ApiUser,
    service: SampleCatalogService,
):
    """Create a sample comment and serialize the change response."""
    sample = _get_sample_for_api(sample_id, user)
    form_data = payload.form_data
    doc = create_comment_doc(form_data, key="sample_comment")
    service.add_sample_comment(sample_id=sample_id, doc=doc)
    result = change_payload(
        sample_id=sample_id, resource="sample_comment", resource_id="new", action="add"
    )
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@router.post(
    "/api/v1/samples/{sample_id}/comments",
    response_model=SampleChangePayload,
    status_code=201,
    summary="Create sample comment",
)
def create_sample_comment(
    sample_id: str,
    payload: SampleCommentCreateRequest,
    user: ApiUser = Depends(
        require_access(permission="add_sample_comment", min_role="user", min_level=9)
    ),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Create a sample comment."""
    return _add_sample_comment(sample_id=sample_id, payload=payload, user=user, service=service)


def _hide_sample_comment(
    sample_id: str, comment_id: str, user: ApiUser, service: SampleCatalogService
):
    """Hide sample comment.

    Args:
            sample_id: Sample id.
            comment_id: Comment id.
            user: User.
    Returns:
            The  hide sample comment result.
    """
    sample = _get_sample_for_api(sample_id, user)
    service.set_sample_comment_hidden(sample_id=sample_id, comment_id=comment_id, hidden=True)
    result = change_payload(
        sample_id=sample_id, resource="sample_comment", resource_id=comment_id, action="hide"
    )
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@router.patch(
    "/api/v1/samples/{sample_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Hide sample comment",
)
def hide_sample_comment(
    sample_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="hide_sample_comment", min_role="manager", min_level=99)
    ),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Hide a sample comment."""
    return _hide_sample_comment(
        sample_id=sample_id, comment_id=comment_id, user=user, service=service
    )


def _unhide_sample_comment(
    sample_id: str, comment_id: str, user: ApiUser, service: SampleCatalogService
):
    """Unhide a sample comment and serialize the change response."""
    sample = _get_sample_for_api(sample_id, user)
    service.set_sample_comment_hidden(sample_id=sample_id, comment_id=comment_id, hidden=False)
    result = change_payload(
        sample_id=sample_id, resource="sample_comment", resource_id=comment_id, action="unhide"
    )
    result["meta"]["omics_layer"] = sample.get("omics_layer")
    return util.common.convert_to_serializable(result)


@router.delete(
    "/api/v1/samples/{sample_id}/comments/{comment_id}/hidden",
    response_model=SampleChangePayload,
    summary="Unhide sample comment",
)
def unhide_sample_comment(
    sample_id: str,
    comment_id: str,
    user: ApiUser = Depends(
        require_access(permission="unhide_sample_comment", min_role="manager", min_level=99)
    ),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Unhide a sample comment."""
    return _unhide_sample_comment(
        sample_id=sample_id, comment_id=comment_id, user=user, service=service
    )


def _update_sample_filters(
    sample_id: str,
    payload: SampleFiltersUpdateRequest,
    user: ApiUser,
    service: SampleCatalogService,
):
    """Update a sample's filters and serialize the change response."""
    sample = _get_sample_for_api(sample_id, user)
    filters = payload.filters
    normalized_filters = dict(filters)
    existing_filters = dict(sample.get("filters") or {})
    if "adhoc_genes" not in normalized_filters and "adhoc_genes" in existing_filters:
        normalized_filters["adhoc_genes"] = existing_filters.get("adhoc_genes")

    if str(sample.get("omics_layer", "")).lower() == "rna":
        normalized_filters = normalize_rna_filter_keys(normalized_filters)
        normalized_filters["fusion_callers"] = create_fusioncallers(
            normalized_filters.get("fusion_callers", [])
        )
        normalized_filters["fusion_effects"] = create_fusioneffectlist(
            normalized_filters.get("fusion_effects", [])
        )
        fusionlists = normalized_filters.get("fusionlists")
        if fusionlists is None:
            normalized_filters["fusionlists"] = []
        elif isinstance(fusionlists, str):
            normalized_filters["fusionlists"] = [fusionlists] if fusionlists else []
        elif isinstance(fusionlists, tuple):
            normalized_filters["fusionlists"] = list(fusionlists)
        normalized_filters["fusionlists"] = list(
            dict.fromkeys(normalized_filters.get("fusionlists", []))
        )
    else:
        normalized_filters = normalize_dna_filter_keys(normalized_filters)

    service.replace_sample_filters(sample=sample, filters=normalized_filters)
    result = change_payload(
        sample_id=sample_id,
        resource="sample_filters",
        resource_id=str(sample.get("_id")),
        action="update",
    )
    return util.common.convert_to_serializable(result)


@router.put(
    "/api/v1/samples/{sample_id}/filters",
    response_model=SampleChangePayload,
    summary="Replace sample filters",
)
def update_sample_filters(
    sample_id: str,
    payload: SampleFiltersUpdateRequest,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Replace a sample's filter payload."""
    return _update_sample_filters(sample_id=sample_id, payload=payload, user=user, service=service)


def _reset_sample_filters(sample_id: str, user: ApiUser, service: SampleCatalogService):
    """Reset a sample's filters and serialize the change response."""
    sample = _get_sample_for_api(sample_id, user)
    assay_config = get_formatted_assay_config(sample)
    if not assay_config:
        raise api_error(404, "Assay config not found for sample")
    service.reset_sample_filters(sample=sample, assay_config=assay_config)
    result = change_payload(
        sample_id=sample_id,
        resource="sample_filters",
        resource_id=str(sample.get("_id")),
        action="reset",
    )
    return util.common.convert_to_serializable(result)


@router.delete(
    "/api/v1/samples/{sample_id}/filters",
    response_model=SampleChangePayload,
    summary="Reset sample filters",
)
def reset_sample_filters(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="edit_sample", min_role="user")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Reset a sample's filters to assay defaults."""
    return _reset_sample_filters(sample_id=sample_id, user=user, service=service)


def _update_coverage_blacklist(
    payload: CoverageBlacklistUpdateRequest, service: SampleCatalogService
):
    """Create a coverage blacklist entry and serialize the response."""
    gene = payload.gene
    coord = payload.coord or ""
    smp_grp = payload.smp_grp
    region = payload.region
    status = payload.status
    if coord:
        coord = str(coord).replace(":", "_").replace("-", "_")
        service.add_coverage_blacklist(gene=gene, coord=coord, region=region, smp_grp=smp_grp)
        return util.common.convert_to_serializable(
            {
                "status": "ok",
                "message": (
                    f" Status for {gene}:{region}:{coord} was set as {status} for group: {smp_grp}. "
                    "Page needs to be reload to take effect"
                ),
            }
        )
    service.add_coverage_blacklist(gene=gene, coord=None, region=region, smp_grp=smp_grp)
    return util.common.convert_to_serializable(
        {
            "status": "ok",
            "message": (
                f" Status for full gene: {gene} was set as {status} for group: {smp_grp}. "
                "Page needs to be reload to take effect"
            ),
        }
    )


@router.post(
    "/api/v1/coverage/blacklist/entries",
    response_model=CoverageBlacklistStatusPayload,
    summary="Create coverage blacklist entry",
)
def create_coverage_blacklist_entry(
    payload: CoverageBlacklistUpdateRequest,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Create a coverage blacklist entry."""
    _ = user
    return _update_coverage_blacklist(payload=payload, service=service)


def _remove_coverage_blacklist(obj_id: str, service: SampleCatalogService):
    """Delete a coverage blacklist entry and serialize the response."""
    service.remove_coverage_blacklist(obj_id=obj_id)
    return util.common.convert_to_serializable(
        change_payload("coverage", resource="blacklist", resource_id=obj_id, action="remove")
    )


@router.delete(
    "/api/v1/coverage/blacklist/entries/{obj_id}",
    response_model=SampleChangePayload,
    summary="Delete coverage blacklist entry",
)
def delete_coverage_blacklist_entry(
    obj_id: str,
    user: ApiUser = Depends(require_access(min_level=1)),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Delete a coverage blacklist entry."""
    _ = user
    return _remove_coverage_blacklist(obj_id=obj_id, service=service)
