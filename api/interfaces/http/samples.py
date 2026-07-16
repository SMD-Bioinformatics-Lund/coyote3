"""Sample and coverage mutation router."""

from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse

from api.app.container import util
from api.app.deps.services import get_sample_catalog_service
from api.app.http import api_error, get_formatted_assay_config
from api.application.common.change_payload import change_payload
from api.application.interpretation.report_summary import create_comment_doc
from api.application.sample.catalog import SampleCatalogService
from api.contracts.home import (
    HomeChangeStatusPayload,
    HomeEditContextPayload,
    HomeEffectiveGenesPayload,
    HomeItemsPayload,
    HomeReportContextPayload,
    HomeSamplesPayload,
)
from api.contracts.samples import (
    CoverageBlacklistUpdateRequest,
    SampleChangePayload,
    SampleCommentCreateRequest,
    SampleFiltersUpdateRequest,
)
from api.domain.common.sample_filters import (
    canonical_dna_filter_section,
    normalize_sample_filters,
    sample_filter_section,
)
from api.domain.core.rna.helpers import create_fusioncallers, create_fusioneffectlist
from api.domain.core.workflows.filter_normalization import (
    normalize_dna_filter_keys,
    normalize_rna_filter_keys,
)
from api.security.access import ApiUser, _get_sample_for_api, require_access

router = APIRouter(tags=["samples"])


def _ensure_coverage_group_access(smp_grp: str, user: ApiUser) -> None:
    """Require the user to be scoped to the coverage assay group."""
    if user.is_superuser:
        return
    if smp_grp not in set(user.assay_groups or []):
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
    user: ApiUser = Depends(require_access()),
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
    existing_filters = normalize_sample_filters(
        sample.get("filters"), omics_layer=str(sample.get("omics_layer") or "dna")
    )

    if str(sample.get("omics_layer", "")).lower() == "rna":
        if isinstance(incoming_filters.get("fusion"), dict):
            normalized_filters = normalize_rna_filter_keys(incoming_filters.get("fusion"))
        else:
            normalized_filters = normalize_rna_filter_keys(incoming_filters)
        existing_fusion_filters = sample_filter_section(
            existing_filters, "fusion", omics_layer="rna"
        )
        if "adhoc_genes" not in normalized_filters and "adhoc_genes" in existing_fusion_filters:
            normalized_filters["adhoc_genes"] = existing_fusion_filters.get("adhoc_genes")
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
        normalized_filters = {"fusion": normalized_filters}
    else:
        if any(
            isinstance(incoming_filters.get(section), dict)
            for section in ("snv", "cnv", "coverage")
        ):
            normalized_filters = {
                "snv": canonical_dna_filter_section(
                    normalize_dna_filter_keys(incoming_filters.get("snv") or {}), "snv"
                ),
                "cnv": canonical_dna_filter_section(
                    normalize_dna_filter_keys(incoming_filters.get("cnv") or {}), "cnv"
                ),
                "coverage": canonical_dna_filter_section(
                    dict(incoming_filters.get("coverage") or {}), "coverage"
                ),
            }
        else:
            normalized_filters = normalize_dna_filter_keys(incoming_filters)
            normalized_filters = normalize_sample_filters(
                normalized_filters, omics_layer=str(sample.get("omics_layer") or "dna")
            )
        for section in ("snv", "cnv"):
            existing_section = sample_filter_section(existing_filters, section, omics_layer="dna")
            if existing_section.get("adhoc_genes"):
                normalized_filters.setdefault(section, {}).setdefault(
                    "adhoc_genes", existing_section.get("adhoc_genes")
                )

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
