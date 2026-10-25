"""Sample and coverage mutation router."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, Query
from fastapi.responses import FileResponse, HTMLResponse

from api.app.container import util
from api.app.deps.application import get_coverage, get_named_sample, get_sample, get_samples
from api.interfaces.http.tags import TAG_CLINICAL_SAMPLES
from api.security.access import ApiUser, require_access
from coyote3.application.common.change_payload import change_payload
from coyote3.application.operations.coverage import Coverage
from coyote3.application.operations.models import FileArtifact, SampleSearch
from coyote3.application.operations.samples import Sample, Samples
from coyote3.config.constants import DEFAULT_ENVIRONMENT
from coyote3.contracts.home import (
    HomeChangeStatusPayload,
    HomeEditContextPayload,
    HomeEffectiveGenesPayload,
    HomeItemsPayload,
    HomeReportContextPayload,
    HomeSamplesPayload,
    SampleNavigationCountsPayload,
)
from coyote3.contracts.resource_fields import FieldValue, SampleField
from coyote3.contracts.resource_metadata import SampleMetadata
from coyote3.contracts.samples import (
    ConfigurationApplyRequest,
    ConfigurationPreviewPayload,
    CoverageBlacklistUpdateRequest,
    SampleBamFilesPayload,
    SampleChangePayload,
    SampleCommentCreateRequest,
    SampleFiltersUpdateRequest,
)

router = APIRouter(tags=[TAG_CLINICAL_SAMPLES])


def _report_response(artifact: FileArtifact, *, attachment: bool):
    """Adapt a validated SDK artifact to the existing download/cache/CSP HTTP contract."""
    headers = {"Cache-Control": "no-store"}
    if artifact.media_type != "application/pdf":
        headers["Content-Security-Policy"] = (
            "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
            "base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
        )
    if attachment or artifact.media_type == "application/pdf":
        return FileResponse(
            artifact.path,
            filename=artifact.filename,
            media_type=artifact.media_type,
            headers=headers,
        )
    if artifact.text is None:
        raise RuntimeError("The artifact adapter did not load inline report content")
    return HTMLResponse(artifact.text, headers=headers)


@router.get("/api/v1/samples", response_model=HomeSamplesPayload)
def list_samples_read(
    status: str = "live",
    search_str: str = "",
    search_mode: str = "live",
    live_sort: str = Query(default=""),
    reported_sort: str = Query(default=""),
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
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Samples = Depends(get_samples),
):
    """Return the sample catalog for the current user."""
    return util.common.convert_to_serializable(
        service.list(
            SampleSearch(
                status=status,
                search_str=search_str,
                search_mode=search_mode,
                live_sort=live_sort,
                reported_sort=reported_sort,
                page=page,
                per_page=per_page,
                live_page=live_page,
                done_page=done_page,
                live_per_page=live_per_page,
                done_per_page=done_per_page,
                profile_scope=profile_scope,
                panel_type=panel_type,
                panel_tech=panel_tech,
                assay_group=assay_group,
                added_from=added_from,
                added_until=added_until,
            )
        )
    )


@router.get("/api/v1/samples/navigation-counts", response_model=SampleNavigationCountsPayload)
def sample_navigation_counts_read(
    profile_scope: str = Query(default=DEFAULT_ENVIRONMENT),
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Samples = Depends(get_samples),
):
    """Return live sample counts for the current user's assay navigation menu."""
    return util.common.convert_to_serializable(
        service.navigation_counts(profile_scope=profile_scope)
    )


@router.get("/api/v1/samples/{sample_id}/metadata", response_model=SampleMetadata)
def sample_metadata_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
):
    """Return permitted sample metadata; requires sample:view and sample scope."""
    return service.metadata()


@router.get("/api/v1/samples/{sample_id}/fields/{field}", response_model=FieldValue)
def sample_field_read(
    sample_id: str,
    field: SampleField,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
):
    """Return one allowed sample value; requires sample:view and sample scope.

    The response intentionally excludes filters, files, patient/case details,
    annotations, findings, and report content.
    """
    return util.common.convert_to_serializable(service.field(field))


@router.get("/api/v1/samples/{sample_id}/genelists", response_model=HomeItemsPayload)
def sample_genelists_read(
    sample_id: str,
    target: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
):
    """Return selectable genelists for a sample."""
    return util.common.convert_to_serializable(service.genelists(target=target))


@router.get("/api/v1/samples/{sample_id}/effective-genes", response_model=HomeEffectiveGenesPayload)
def sample_effective_genes_read(
    sample_id: str,
    target: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
):
    """Return the effective genes for a sample."""
    return util.common.convert_to_serializable(service.effective_genes(target=target))


@router.get("/api/v1/samples/{sample_name}/bam-files", response_model=SampleBamFilesPayload)
def sample_bam_files_read(
    sample_name: str,
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_named_sample),
):
    """Return BAM-service file paths for the case/control IDs of a named sample."""
    return util.common.convert_to_serializable(service.bam_files())


@router.get("/api/v1/samples/{sample_id}/edit-context", response_model=HomeEditContextPayload)
def sample_edit_context_read(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: Sample = Depends(get_sample),
):
    """Return edit context for a sample."""
    return util.common.convert_to_serializable(service.edit_context())


@router.put(
    "/api/v1/samples/{sample_id}/genelists/selection", response_model=HomeChangeStatusPayload
)
def sample_apply_genelists_change(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    target: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: Sample = Depends(get_sample),
):
    """Persist selected genelists for a sample."""
    return util.common.convert_to_serializable(service.apply_genelists(payload, target=target))


@router.put("/api/v1/samples/{sample_id}/adhoc-genes", response_model=HomeChangeStatusPayload)
def sample_save_adhoc_genes_change(
    sample_id: str,
    payload: dict = Body(default_factory=dict),
    target: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: Sample = Depends(get_sample),
):
    """Persist ad hoc genes for a sample."""
    return util.common.convert_to_serializable(service.save_adhoc_genes(payload, target=target))


@router.delete("/api/v1/samples/{sample_id}/adhoc-genes", response_model=HomeChangeStatusPayload)
def sample_clear_adhoc_genes_change(
    sample_id: str,
    target: str | None = Query(default=None),
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: Sample = Depends(get_sample),
):
    """Clear ad hoc genes for a sample."""
    return util.common.convert_to_serializable(service.clear_adhoc_genes(target=target))


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_id}/context",
    response_model=HomeReportContextPayload,
)
def sample_report_context_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="report:view")),
    service: Sample = Depends(get_sample),
):
    """Return report-download context for a sample report."""
    return util.common.convert_to_serializable(service.report_context(report_id))


@router.get("/api/v1/samples/{sample_id}/plots/{filename}", response_class=FileResponse)
def sample_plot_read(
    sample_id: str,
    filename: str,
    rotated: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="sample:view")),
    service: Sample = Depends(get_sample),
):
    """Serve only the registered CNV profile belonging to the authorized sample.

    Args:
        sample_id: Sample whose access scope is checked before resolving artifacts.
        filename: Exact basename recorded in that sample's CNV profile path.
        rotated: Reserved display option; does not change the selected artifact.
        user: Authenticated caller checked against the sample's scope.

    Returns:
        Non-cacheable raster image response for the registered file.

    Raises:
        AppError: If sample access is denied, the registered file is absent or
            mismatched (404), or the media type is not a raster image (415).
    """
    artifact = service.plot(filename)
    return FileResponse(
        artifact.path,
        media_type=artifact.media_type,
        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/api/v1/samples/{sample_id}/reports/{report_id}/html", response_class=HTMLResponse)
def sample_report_html_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="report:view")),
    service: Sample = Depends(get_sample),
):
    """Return saved sample report HTML."""
    return _report_response(service.report_artifact(report_id, inline=True), attachment=False)


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_id}/download",
    response_class=FileResponse,
)
def sample_report_download_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="report:view")),
    service: Sample = Depends(get_sample),
):
    """Download saved sample report HTML."""
    return _report_response(service.report_artifact(report_id), attachment=True)


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_id}/pdf",
    response_class=FileResponse,
)
def sample_report_pdf_download_read(
    sample_id: str,
    report_id: str,
    user: ApiUser = Depends(require_access(permission="report:view")),
    service: Sample = Depends(get_sample),
):
    """Download saved sample report PDF."""
    return _report_response(service.report_artifact(report_id, file_type="pdf"), attachment=True)


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
    service: Sample = Depends(get_sample),
):
    """Create a sample comment."""
    mutation = service.add_comment(payload.form_data)
    result = change_payload(
        sample_id=sample_id,
        resource="sample_comment",
        resource_id=mutation.resource_id,
        action="add",
    )
    result["meta"]["asp_category"] = mutation.asp_category
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
    service: Sample = Depends(get_sample),
):
    """Hide a sample comment."""
    mutation = service.set_comment_hidden(comment_id, hidden=True)
    result = change_payload(
        sample_id=sample_id,
        resource="sample_comment",
        resource_id=mutation.resource_id,
        action="hide",
    )
    result["meta"]["asp_category"] = mutation.asp_category
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
    service: Sample = Depends(get_sample),
):
    """Unhide a sample comment."""
    mutation = service.set_comment_hidden(comment_id, hidden=False)
    result = change_payload(
        sample_id=sample_id,
        resource="sample_comment",
        resource_id=mutation.resource_id,
        action="unhide",
    )
    result["meta"]["asp_category"] = mutation.asp_category
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
    service: Sample = Depends(get_sample),
):
    """Replace a sample's filter payload."""
    mutation = service.update_filters(payload.filters)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="sample_filters",
            resource_id=mutation.resource_id,
            action="update",
        )
    )


@router.delete(
    "/api/v1/samples/{sample_id}/filters",
    response_model=SampleChangePayload,
    summary="Reset sample filters",
)
def reset_sample_filters(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: Sample = Depends(get_sample),
):
    """Reset a sample's filters to assay defaults."""
    mutation = service.reset_filters()
    return util.common.convert_to_serializable(
        change_payload(
            sample_id=sample_id,
            resource="sample_filters",
            resource_id=mutation.resource_id,
            action="reset",
        )
    )


@router.get("/api/v1/samples/{sample_id}/aspc/preview", response_model=ConfigurationPreviewPayload)
def preview_sample_aspc(
    sample_id: str,
    retain_overrides: bool = False,
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: Sample = Depends(get_sample),
):
    """Preview configuration changes for an accessible sample without changing its settings."""
    return util.common.convert_to_serializable(
        service.preview_configuration(retain_overrides=retain_overrides)
    )


@router.post(
    "/api/v1/samples/{sample_id}/aspc/apply-latest",
    response_model=SampleChangePayload,
    summary="Apply latest ASPC revision to a sample",
)
def apply_latest_sample_aspc(
    sample_id: str,
    payload: ConfigurationApplyRequest,
    user: ApiUser = Depends(require_access(permission="sample:edit:own")),
    service: Sample = Depends(get_sample),
):
    """Replace a sample's stored ASPC snapshot only after an explicit user action."""
    mutation = service.apply_configuration(payload)
    result = change_payload(
        sample_id=sample_id,
        resource="sample_aspc",
        resource_id=mutation.resource_id,
        action="apply_latest",
    )
    result["meta"] = mutation.details
    return util.common.convert_to_serializable(result)


@router.post(
    "/api/v1/coverage/blacklist/entries",
    response_model=SampleChangePayload,
    summary="Create coverage blacklist entry",
)
def create_coverage_blacklist_entry(
    payload: CoverageBlacklistUpdateRequest,
    user: ApiUser = Depends(require_access(permission="coverage.blacklist:manage")),
    service: Coverage = Depends(get_coverage),
):
    """Create a coverage blacklist entry."""
    identity = service.add_blacklist(
        gene=payload.gene, coordinate=payload.coord, group=payload.smp_grp, region=payload.region
    )
    return util.common.convert_to_serializable(
        change_payload(
            sample_id="coverage", resource="blacklist", resource_id=identity, action="add"
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
    service: Coverage = Depends(get_coverage),
):
    """Delete a coverage blacklist entry."""
    service.remove_blacklist(obj_id)
    return util.common.convert_to_serializable(
        change_payload(
            sample_id="coverage", resource="blacklist", resource_id=obj_id, action="remove"
        )
    )
