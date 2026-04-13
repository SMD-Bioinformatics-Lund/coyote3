"""Canonical report router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.reports import ReportPreviewPayload, ReportSavePayload
from api.deps.services import get_dna_workflow_service, get_rna_workflow_service
from api.extensions import util
from api.http import api_error as _api_error
from api.http import get_formatted_assay_config as _get_formatted_assay_config
from api.runtime_state import app as runtime_app
from api.runtime_state import current_username
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.reporting.report_builder import ReportAnalyte, ReportService
from api.settings import to_bool

router = APIRouter(tags=["reports"])


def _normalize_rendered_report_payload(report_payload: dict | None) -> tuple[str, list]:
    """Validate and normalize a rendered report payload.

    Args:
        report_payload: Rendered report payload from the workflow layer.

    Returns:
        tuple[str, list]: Rendered HTML and snapshot rows.
    """
    payload = report_payload or {}
    html = payload.get("html") or ""
    snapshot_rows = payload.get("snapshot_rows")
    if snapshot_rows is None:
        snapshot_rows = []
    if not isinstance(html, str) or not html.strip():
        raise _api_error(400, "Missing rendered report html")
    if not isinstance(snapshot_rows, list):
        raise _api_error(400, "Invalid snapshot_rows payload")
    return html, snapshot_rows


report_service = ReportService()


def _load_report_context(sample_id: str, user: ApiUser) -> tuple[dict, dict]:
    """Load the sample and assay-config context for report generation.

    Args:
        sample_id: Sample identifier to load.
        user: Authenticated user requesting the report.

    Returns:
        tuple[dict, dict]: Sample payload and assay-config payload.
    """
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(
            422,
            "ASPC could not be resolved for the sample",
            (
                f"Sample '{sample.get('name', sample_id)}' could not resolve an assay "
                "configuration during report generation."
            ),
            category="setup",
        )
    return sample, assay_config


def _validate_report_inputs(analyte: ReportAnalyte, sample: dict, assay_config: dict) -> None:
    """Validate report prerequisites for the selected analyte.

    Args:
        analyte: Report analyte being rendered.
        sample: Sample payload being reported.
        assay_config: Assay-config payload for the sample.
    """
    if analyte == "dna":
        get_dna_workflow_service().validate_report_inputs(runtime_app.logger, sample, assay_config)
    else:
        get_rna_workflow_service().validate_report_inputs(runtime_app.logger, sample, assay_config)


def _build_preview_report(
    analyte: ReportAnalyte, sample: dict, assay_config: dict, *, save: bool, include_snapshot: bool
):
    """Build a rendered preview payload for a report.

    Args:
        analyte: Report analyte being rendered.
        sample: Sample payload being reported.
        assay_config: Assay-config payload for the sample.
        save: Whether the report should be rendered in save mode.
        include_snapshot: Whether snapshot rows should be included.

    Returns:
        dict: Rendered report payload from the workflow layer.
    """
    if analyte == "dna":
        return get_dna_workflow_service().build_report_payload(
            sample=sample,
            assay_config=assay_config,
            save=1 if save else 0,
            include_snapshot=include_snapshot,
        )
    return get_rna_workflow_service().build_report_payload(
        sample=sample,
        save=1 if save else 0,
        include_snapshot=include_snapshot,
    )


def _build_report_location(
    analyte: ReportAnalyte, sample: dict, assay_config: dict
) -> tuple[str, str, str]:
    """Resolve the filesystem location for a report output.

    Args:
        analyte: Report analyte being rendered.
        sample: Sample payload being reported.
        assay_config: Assay-config payload for the sample.

    Returns:
        tuple[str, str, str]: Report directory, file path, and report filename.
    """
    base_path = runtime_app.config.get("REPORTS_BASE_PATH", "reports")
    if analyte == "dna":
        return get_dna_workflow_service().build_report_location(
            sample=sample,
            assay_config=assay_config,
            reports_base_path=base_path,
        )
    return get_rna_workflow_service().build_report_location(
        sample=sample,
        assay_config=assay_config,
        reports_base_path=base_path,
    )


def _prepare_report_output(analyte: ReportAnalyte, report_path: str, report_file: str) -> None:
    """Prepare the output location for a rendered report.

    Args:
        analyte: Report analyte being rendered.
        report_path: Target report directory.
        report_file: Target report filename.
    """
    if analyte == "dna":
        get_dna_workflow_service().prepare_report_output(
            report_path, report_file, logger=runtime_app.logger
        )
    else:
        get_rna_workflow_service().prepare_report_output(
            report_path, report_file, logger=runtime_app.logger
        )


def _persist_report(
    analyte: ReportAnalyte,
    *,
    sample_id: str,
    sample: dict,
    report_num: int,
    report_id: str,
    report_file: str,
    html: str,
    snapshot_rows: list,
    created_by: str,
) -> str:
    """Persist a rendered report through the workflow layer.

    Args:
        analyte: Report analyte being rendered.
        sample_id: Sample identifier being reported.
        sample: Sample payload being reported.
        report_num: Sequential report number.
        report_id: Logical report identifier.
        report_file: Saved report filename.
        html: Rendered report HTML.
        snapshot_rows: Snapshot rows extracted from the report.
        created_by: Username saving the report.

    Returns:
        str: Persisted report object identifier.
    """
    if analyte == "dna":
        return get_dna_workflow_service().persist_report(
            sample_id=sample_id,
            sample=sample,
            report_num=report_num,
            report_id=report_id,
            report_file=report_file,
            html=html,
            snapshot_rows=snapshot_rows,
            created_by=created_by,
        )
    return get_rna_workflow_service().persist_report(
        sample_id=sample_id,
        sample=sample,
        report_num=report_num,
        report_id=report_id,
        report_file=report_file,
        html=html,
        snapshot_rows=snapshot_rows,
        created_by=created_by,
    )


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_type}/preview",
    response_model=ReportPreviewPayload,
    summary="Preview sample report",
)
def preview_report(
    sample_id: str,
    report_type: ReportAnalyte,
    include_snapshot: bool = Query(default=False),
    save: bool = Query(default=False),
    user: ApiUser = Depends(
        require_access(permission="report:preview", min_role="user", min_level=9)
    ),
):
    """Render a report preview for a sample."""
    sample, assay_config = _load_report_context(sample_id, user)
    _validate_report_inputs(report_type, sample, assay_config)

    template_name, template_context, snapshot_rows = _build_preview_report(
        report_type,
        sample,
        assay_config,
        save=to_bool(save, default=False),
        include_snapshot=to_bool(include_snapshot, default=False),
    )
    snapshot_rows = snapshot_rows or []
    payload = report_service.preview_payload(
        sample=sample,
        request_path=f"/api/v1/samples/{sample_id}/reports/{report_type}/preview",
        include_snapshot=include_snapshot,
        template_name=template_name,
        template_context=template_context,
        snapshot_rows=snapshot_rows,
    )
    return util.common.convert_to_serializable(payload)


@router.post(
    "/api/v1/samples/{sample_id}/reports/{report_type}",
    response_model=ReportSavePayload,
    status_code=201,
    summary="Create sample report",
)
def save_report(
    sample_id: str,
    report_type: ReportAnalyte,
    report_payload: dict | None = Body(default=None),
    user: ApiUser = Depends(require_access(permission="report:create", min_role="admin")),
):
    """Persist a rendered sample report."""
    sample, assay_config = _load_report_context(sample_id, user)
    _validate_report_inputs(report_type, sample, assay_config)

    report_num = sample.get("report_num", 0) + 1
    report_id, report_path, report_file = _build_report_location(report_type, sample, assay_config)
    _prepare_report_output(report_type, report_path, report_file)

    html, snapshot_rows = _normalize_rendered_report_payload(report_payload)

    report_oid = _persist_report(
        report_type,
        sample_id=sample_id,
        sample=sample,
        report_num=report_num,
        report_id=report_id,
        report_file=report_file,
        html=html,
        snapshot_rows=snapshot_rows,
        created_by=current_username(),
    )

    payload = report_service.save_payload(
        sample=sample,
        report_id=report_id,
        report_oid=str(report_oid),
        report_file=report_file,
        snapshot_rows=snapshot_rows,
    )
    response_payload = util.common.convert_to_serializable(payload)
    return response_payload
