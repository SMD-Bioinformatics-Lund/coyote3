"""Sample and coverage mutation router."""

from __future__ import annotations

import mimetypes
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse

from api.app.container import util
from api.app.deps.services import get_common_query_service, get_sample_catalog_service
from api.app.http import api_error, get_formatted_assay_config
from api.application.common.change_payload import change_payload
from api.application.common.query_service import CommonQueryService
from api.application.interpretation.report_summary import create_comment_doc
from api.application.sample.catalog import SampleCatalogService
from api.config.constants import DEFAULT_ENVIRONMENT, primary_analysis_file_key
from api.contracts.home import (
    HomeChangeStatusPayload,
    HomeEditContextPayload,
    HomeEffectiveGenesPayload,
    HomeItemsPayload,
    HomeReportContextPayload,
    HomeSamplesPayload,
    SampleNavigationCountsPayload,
)
from api.contracts.samples import (
    CoverageBlacklistUpdateRequest,
    SampleBamFilesPayload,
    SampleChangePayload,
    SampleCommentCreateRequest,
    SampleFiltersUpdateRequest,
)
from api.domain.common.sample_filters import normalize_sample_filters
from api.interfaces.http.tags import TAG_CLINICAL_SAMPLES
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=[TAG_CLINICAL_SAMPLES])


def _ensure_coverage_group_access(smp_grp: str, user: ApiUser) -> None:
    """Require the user to be scoped to the coverage assay group."""
    if user.is_superuser:
        return
    if smp_grp not in set(user.asp_groups or []):
        raise api_error(
            403,
            f"Assay group '{smp_grp}' is outside your scope",
            f"User '{user.username}' is not assigned to assay group '{smp_grp}'.",
            category="scope",
            hint="Ask an administrator to assign the assay group, or use a superuser account.",
        )


@router.get("/api/v1/samples", response_model=HomeSamplesPayload)
def list_samples_read(
    status: str = "live",
    search_str: str = "",
    search_mode: str = "live",
    live_sort: str = Query(default=""),
    reported_sort: str = Query(default=""),
    sample_view: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    live_page: int = Query(default=1, ge=1),
    done_page: int = Query(default=1, ge=1),
    live_per_page: int | None = Query(default=None, ge=1, le=200),
    done_per_page: int | None = Query(default=None, ge=1, le=200),
    profile_scope: str = Query(default=DEFAULT_ENVIRONMENT),
    panel_type: str | None = None,
    panel_tech: str | None = None,
    assay_group: str | None = None,
    added_from: datetime | None = None,
    added_until: datetime | None = None,
    user: ApiUser = Depends(require_access()),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return the sample catalog for the current user."""
    _ = sample_view
    live_per_page = live_per_page or per_page
    done_per_page = done_per_page or per_page
    if added_from and added_until and added_until <= added_from:
        raise api_error(
            400,
            "Invalid sample date range",
            "added_until must be later than added_from.",
            category="validation",
        )
    return util.common.convert_to_serializable(
        service.samples_payload(
            user=user,
            status=status,
            search_str=search_str,
            search_mode=search_mode,
            live_sort=live_sort,
            reported_sort=reported_sort,
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
            added_from=added_from,
            added_until=added_until,
        )
    )


@router.get("/api/v1/samples/navigation-counts", response_model=SampleNavigationCountsPayload)
def sample_navigation_counts_read(
    profile_scope: str = Query(default=DEFAULT_ENVIRONMENT),
    user: ApiUser = Depends(require_access()),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return live sample counts for the current user's assay navigation menu."""
    return util.common.convert_to_serializable(
        service.navigation_counts_payload(user=user, profile_scope=profile_scope)
    )


@router.get("/api/v1/samples/{sample_id}/genelists", response_model=HomeItemsPayload)
def sample_genelists_read(
    sample_id: str,
    target: str | None = Query(default=None),
    user: ApiUser = Depends(require_access()),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return selectable genelists for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.genelist_items_payload(sample=sample, target=target)
    )


@router.get("/api/v1/samples/{sample_id}/effective-genes", response_model=HomeEffectiveGenesPayload)
def sample_effective_genes_read(
    sample_id: str,
    target: str | None = Query(default=None),
    user: ApiUser = Depends(require_access()),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return the effective genes for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.effective_genes_payload(sample=sample, target=target)
    )


@router.get("/api/v1/samples/{sample_name}/bam-files", response_model=SampleBamFilesPayload)
def sample_bam_files_read(
    sample_name: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: CommonQueryService = Depends(get_common_query_service),
):
    """Return BAM-service file paths for the case/control IDs of a named sample."""
    sample = _get_sample_for_api(sample_name, user)
    sample_ids = [
        str(sample.get("case", {}).get("id") or sample.get("case_id") or "").strip(),
        str(sample.get("control", {}).get("id") or sample.get("control_id") or "").strip(),
    ]
    sample_ids = [sample_id for sample_id in sample_ids if sample_id]
    if not sample_ids:
        raise api_error(404, "No case or control sample IDs are available for this sample")
    payload = service.bam_files_payload(sample_ids=sample_ids)
    return util.common.convert_to_serializable(
        {
            **payload,
            "sample": {
                "name": sample.get("name") or sample_name,
                "case_id": sample.get("case", {}).get("id") or sample.get("case_id"),
                "control_id": sample.get("control", {}).get("id") or sample.get("control_id"),
                "paired": bool(sample.get("paired")),
            },
        }
    )


@router.get("/api/v1/samples/{sample_id}/edit-context", response_model=HomeEditContextPayload)
def sample_edit_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
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
    target: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Persist selected genelists for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.apply_genelists(sample=sample, payload=payload, sample_id=sample_id, target=target)
    )


@router.put("/api/v1/samples/{sample_id}/adhoc-genes", response_model=HomeChangeStatusPayload)
def sample_save_adhoc_genes_change(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    target: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Persist ad hoc genes for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.save_adhoc_genes(sample=sample, payload=payload, sample_id=sample_id, target=target)
    )


@router.delete("/api/v1/samples/{sample_id}/adhoc-genes", response_model=HomeChangeStatusPayload)
def sample_clear_adhoc_genes_change(
    sample_id: str,
    target: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Clear ad hoc genes for a sample."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.clear_adhoc_genes(sample=sample, sample_id=sample_id, target=target)
    )


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_id}/context",
    response_model=HomeReportContextPayload,
)
def sample_report_context_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="report:view")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return report-download context for a sample report."""
    sample = _get_sample_for_api(sample_id, user)
    return util.common.convert_to_serializable(
        service.report_context_payload(sample=sample, report_id=report_id, sample_id=sample_id)
    )


def _sample_report_file_response(
    *,
    sample_id: str,
    report_id: str,
    user: ApiUser,
    service: SampleCatalogService,
    as_attachment: bool,
    file_type: str = "html",
):
    """Resolve and serve a saved sample report file."""
    sample = _get_sample_for_api(sample_id, user)
    context = service.report_context_payload(
        sample=sample, report_id=report_id, sample_id=sample_id
    )
    if file_type == "pdf":
        filepath = context.get("pdf_filepath")
        filename = context.get("pdf_report_name")
        media_type = "application/pdf"
    else:
        filepath = context.get("filepath")
        filename = context.get("report_name")
        media_type = "text/html"
    if not filepath:
        raise api_error(404, "Report file path is not available")
    path = Path(str(filepath))
    if not path.exists() or not path.is_file():
        raise api_error(404, "Report file not found")
    filename = filename or path.name
    if file_type == "pdf":
        return FileResponse(path, filename=filename, media_type=media_type)
    if as_attachment:
        return FileResponse(path, filename=filename, media_type=media_type)
    return HTMLResponse(path.read_text(encoding="utf-8", errors="replace"))


def _safe_file_under(base_dir: str | None, filename: str) -> Path:
    """Resolve a user-facing file name inside a configured directory."""
    if not base_dir:
        raise api_error(404, "Plot directory is not configured")
    base = Path(base_dir).expanduser().resolve()
    path = (base / Path(filename).name).resolve()
    if base not in path.parents and path != base:
        raise api_error(400, "Invalid plot file path")
    if not path.exists() or not path.is_file():
        raise api_error(404, "Plot file not found")
    return path


@router.get("/api/v1/samples/{sample_id}/plots/{filename}", response_class=FileResponse)
def sample_plot_read(
    sample_id: str,
    filename: str,
    rotated: bool = Query(default=False),
    user: ApiUser = Depends(require_access()),
):
    """Serve a configured sample plot image."""
    _ = rotated
    sample = _get_sample_for_api(sample_id, user)
    sample_files = sample.get("files") if isinstance(sample.get("files"), dict) else {}
    cnv_profile = sample_files.get(primary_analysis_file_key("dna", "CNV_PROFILE"))
    if isinstance(cnv_profile, dict) and cnv_profile.get("path"):
        cnv_profile_path = Path(str(cnv_profile["path"])).expanduser().resolve()
        if cnv_profile_path.name == Path(filename).name:
            if not cnv_profile_path.exists() or not cnv_profile_path.is_file():
                raise api_error(404, "CNV profile image file is not available")
            media_type = (
                mimetypes.guess_type(cnv_profile_path.name)[0] or "application/octet-stream"
            )
            return FileResponse(cnv_profile_path, media_type=media_type)
    assay_config = get_formatted_assay_config(sample)
    reporting = assay_config.get("reporting") or assay_config.get("REPORT") or {}
    plot_path = reporting.get("plots_path") or reporting.get("plot_path")
    path = _safe_file_under(plot_path, filename)
    media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.get("/api/v1/samples/{sample_id}/reports/{report_id}/html", response_class=HTMLResponse)
def sample_report_html_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="report:view")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Return saved sample report HTML."""
    return _sample_report_file_response(
        sample_id=sample_id,
        report_id=report_id,
        user=user,
        service=service,
        as_attachment=False,
    )


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_id}/download",
    response_class=FileResponse,
)
def sample_report_download_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="report:view")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Download saved sample report HTML."""
    return _sample_report_file_response(
        sample_id=sample_id,
        report_id=report_id,
        user=user,
        service=service,
        as_attachment=True,
    )


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_id}/pdf",
    response_class=FileResponse,
)
def sample_report_pdf_download_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="report:view")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Download saved sample report PDF."""
    return _sample_report_file_response(
        sample_id=sample_id,
        report_id=report_id,
        user=user,
        service=service,
        as_attachment=True,
        file_type="pdf",
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
    user: ApiUser = Depends(require_access(permission="sample.comment:add")),
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
    user: ApiUser = Depends(require_access(permission="sample.comment:hide")),
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
    user: ApiUser = Depends(require_access(permission="sample.comment:unhide")),
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
    incoming_filters = dict(filters or {})
    analysis_intents = sample.get("analysis_intents") or ["somatic"]
    existing_profiles = normalize_sample_filters(
        sample.get("filters"),
        omics_layer=str(sample.get("omics_layer") or "dna"),
        analysis_intents=analysis_intents,
        canonical=True,
    )
    if not any(key in incoming_filters for key in ("somatic", "germline")):
        raise api_error(
            422,
            "Filters must use the canonical intent profile structure",
            "Submit filters.somatic.<analysis> and, where enabled, filters.germline.snv.",
            category="validation",
        )

    merged_profiles = dict(existing_profiles)
    for intent, profile in incoming_filters.items():
        if intent not in {"somatic", "germline"} or not isinstance(profile, dict):
            continue
        merged_profiles[intent] = {**dict(existing_profiles.get(intent) or {}), **profile}
    normalized_profiles = normalize_sample_filters(
        merged_profiles,
        omics_layer=str(sample.get("omics_layer") or "dna"),
        analysis_intents=analysis_intents,
        canonical=True,
    )
    service.replace_sample_filters(sample=sample, filters=normalized_profiles)
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
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Replace a sample's filter payload."""
    return _update_sample_filters(sample_id=sample_id, payload=payload, user=user, service=service)


def _reset_sample_filters(sample_id: str, user: ApiUser, service: SampleCatalogService):
    """Reset a sample's filters and serialize the change response."""
    sample = _get_sample_for_api(sample_id, user)
    assay_config = get_formatted_assay_config(sample)
    if not assay_config:
        raise api_error(
            422,
            "ASPC could not be resolved for the sample",
            (
                f"Sample '{sample.get('name', sample_id)}' could not resolve an assay "
                "configuration while resetting sample filters."
            ),
            category="setup",
            hint="Create the ASP and ASPC for this assay/profile before resetting filters.",
        )
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
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Reset a sample's filters to assay defaults."""
    return _reset_sample_filters(sample_id=sample_id, user=user, service=service)


@router.post(
    "/api/v1/samples/{sample_id}/aspc/apply-latest",
    response_model=SampleChangePayload,
    summary="Apply latest ASPC revision to a sample",
)
def apply_latest_sample_aspc(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Replace a sample's stored ASPC snapshot only after an explicit user action."""
    sample = _get_sample_for_api(sample_id, user)
    applied = service.apply_latest_aspc(sample=sample)
    result = change_payload(
        sample_id=sample_id,
        resource="sample_aspc",
        resource_id=str(sample.get("_id")),
        action="apply_latest",
    )
    result["meta"] = {"applied_aspc": applied}
    return util.common.convert_to_serializable(result)


@router.post(
    "/api/v1/coverage/blacklist/entries",
    response_model=SampleChangePayload,
    summary="Create coverage blacklist entry",
)
def create_coverage_blacklist_entry(
    payload: CoverageBlacklistUpdateRequest,
    user: ApiUser = Depends(require_access(permission="coverage.blacklist:manage")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Create a coverage blacklist entry."""
    gene = payload.gene
    coord = payload.coord or ""
    smp_grp = payload.smp_grp
    region = payload.region
    _ensure_coverage_group_access(smp_grp, user)
    if coord:
        coord = str(coord).replace(":", "_").replace("-", "_")
    service.add_coverage_blacklist(
        gene=gene, coord=coord if coord else None, region=region, smp_grp=smp_grp
    )
    resource_id = f"{gene}:{region}:{coord}" if coord else f"{gene}:{region}"
    return util.common.convert_to_serializable(
        change_payload(
            sample_id="coverage",
            resource="blacklist",
            resource_id=resource_id,
            action="add",
        )
    )


@router.delete(
    "/api/v1/coverage/blacklist/entries/{obj_id}",
    response_model=SampleChangePayload,
    summary="Delete coverage blacklist entry",
)
def delete_coverage_blacklist_entry(
    obj_id: str,
    user: ApiUser = Depends(require_access(permission="coverage.blacklist:manage")),
    service: SampleCatalogService = Depends(get_sample_catalog_service),
):
    """Delete a coverage blacklist entry."""
    try:
        entry = service.get_coverage_blacklist_entry(obj_id=obj_id)
    except Exception as exc:
        raise api_error(
            400,
            "Invalid coverage blacklist entry id",
            str(exc),
            category="validation",
        ) from exc
    if not entry:
        raise api_error(
            404,
            "Coverage blacklist entry not found",
            f"No coverage blacklist entry exists for id '{obj_id}'.",
            category="not_found",
        )
    _ensure_coverage_group_access(str(entry.get("group") or ""), user)
    service.remove_coverage_blacklist(obj_id=obj_id)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id="coverage",
            resource="blacklist",
            resource_id=obj_id,
            action="remove",
        )
    )
