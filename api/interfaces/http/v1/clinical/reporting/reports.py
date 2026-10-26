"""HTTP adapters for the authoritative application SDK report operations."""

from base64 import b64encode

from fastapi import APIRouter, Depends, Query, Response

from api.app.container import util
from api.app.deps.application import get_application
from api.contracts.report_trials import ReportTrialPayload
from api.interfaces.http.tags import TAG_REPORTING
from api.interfaces.http.v1.clinical.reporting.presenters import ReportPresenter
from api.security.access import ApiUser, require_access
from coyote3.application.operations import CoyoteApplication
from coyote3.application.operations.reporting import Analyte
from coyote3.contracts.reports import (
    ReportLibraryPayload,
    ReportPreviewPayload,
    ReportSavePayload,
    ReportSaveRequest,
)

router = APIRouter(tags=[TAG_REPORTING])


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_type}/try-new",
    response_model=ReportTrialPayload,
    summary="Try the alternate report format without saving",
)
def try_new_report(
    sample_id: str,
    report_type: Analyte,
    response: Response,
    user: ApiUser = Depends(require_access(permission="report:preview")),
    application: CoyoteApplication = Depends(get_application),
):
    """Generate matching temporary HTML/PDF content; requires report:preview and sample scope.

    Neither representation is registered or written as a report artifact. Both
    are returned in this response for browser preview and local download.
    """
    trial = application.reports.try_new(sample_id, report_type)
    response.headers["Cache-Control"] = "no-store"
    return ReportTrialPayload(
        html=trial.html,
        pdf_base64=b64encode(trial.pdf).decode("ascii"),
        filename=trial.filename,
        snapshot_count=trial.snapshot_count,
        reporting_warning=trial.reporting_warning,
    )


@router.get(
    "/api/v1/reports", response_model=ReportLibraryPayload, summary="List saved clinical reports"
)
def list_saved_reports(
    search: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, ge=1, le=200),
    user: ApiUser = Depends(require_access(permission="report:view")),
    application: CoyoteApplication = Depends(get_application),
):
    """Return saved report summaries within current sample scope; requires report:view."""
    result = application.reports.list(search=search, page=page, per_page=per_page)
    return util.common.convert_to_serializable({"reports": result.items, **result.pagination})


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_type}/preview",
    response_model=ReportPreviewPayload,
    summary="Preview sample report",
)
def preview_report(
    sample_id: str,
    report_type: Analyte,
    include_snapshot: bool = Query(default=False),
    save: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="report:preview")),
    application: CoyoteApplication = Depends(get_application),
):
    """Render an authorized report preview; requires report:preview.

    The save flag selects presentation context and does not persist a report.
    """
    result = application.reports.preview(
        sample_id, report_type, include_snapshot=include_snapshot, save_context=save
    )
    return util.common.convert_to_serializable(
        ReportPresenter.preview_payload(
            sample=result.sample,
            request_path=f"/api/v1/samples/{sample_id}/reports/{report_type}/preview",
            include_snapshot=include_snapshot,
            template_name=result.template,
            template_context=result.context,
            html=result.html,
            snapshot_rows=result.snapshot_rows,
            fingerprint=result.fingerprint,
            snapshot_count=result.snapshot_count,
        )
    )


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_type}/preview/pdf",
    response_class=Response,
    summary="Download sample report preview as PDF",
)
def preview_report_pdf(
    sample_id: str,
    report_type: Analyte,
    include_snapshot: bool = Query(default=True),
    user: ApiUser = Depends(require_access(permission="report:preview")),
    application: CoyoteApplication = Depends(get_application),
):
    """Download a current report preview without persisting it; requires report:preview."""
    artifact = application.reports.preview_pdf(
        sample_id, report_type, include_snapshot=include_snapshot
    )
    return Response(
        content=artifact.content,
        media_type=artifact.media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{artifact.filename}"',
            "Cache-Control": "no-store",
        },
    )


@router.post(
    "/api/v1/samples/{sample_id}/reports/{report_type}",
    response_model=ReportSavePayload,
    status_code=201,
    summary="Create sample report",
)
def save_report(
    sample_id: str,
    report_type: Analyte,
    payload: ReportSaveRequest,
    user: ApiUser = Depends(require_access(permission="report:create")),
    application: CoyoteApplication = Depends(get_application),
):
    """Save the reviewed report with snapshots and artifacts; requires report:create.

    A stale preview fingerprint returns 409 before artifact creation.
    """
    result = application.reports.save(
        sample_id, report_type, fingerprint=payload.preview_fingerprint
    )
    return util.common.convert_to_serializable(
        ReportPresenter.save_payload(
            sample=result.sample,
            report_id=result.id,
            report_oid=result.storage_id,
            report_file=result.file,
            pdf_file=result.pdf_file,
            snapshot_count=result.snapshot_count,
        )
    )
