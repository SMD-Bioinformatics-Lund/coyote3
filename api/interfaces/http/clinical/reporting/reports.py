"""Canonical report router module."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response

from api.app.container import util
from api.app.deps.services import get_dna_workflow_service, get_rna_workflow_service
from api.app.http import api_error as _api_error
from api.app.http import get_formatted_assay_config as _get_formatted_assay_config
from api.app.runtime_state import app as runtime_app
from api.app.runtime_state import current_username
from api.application.reporting.report_builder import ReportAnalyte, ReportService
from api.application.reporting.report_renderer import render_pdf_bytes, render_report_html
from api.contracts.reports import ReportPreviewPayload, ReportSavePayload
from api.interfaces.http.tags import TAG_REPORTING
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.settings import to_bool

router = APIRouter(tags=[TAG_REPORTING])


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
        assay_config=assay_config,
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


def _next_report_num(analyte: ReportAnalyte, sample: dict) -> int:
    """Return the next report number from the analyte workflow service."""
    sample_oid = str(sample.get("_id"))
    if analyte == "dna":
        return get_dna_workflow_service().next_report_num(sample_oid)
    return get_rna_workflow_service().next_report_num(sample_oid)


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
    rule_provenance: dict | None = None,
) -> tuple[str, str]:
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
        tuple[str, str]: Persisted report object identifier and PDF file path.
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
            rule_provenance=rule_provenance,
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
        rule_provenance=rule_provenance,
    )


def _clinical_rule_provenance(template_context: dict) -> dict | None:
    """Extract immutable release identity and matched rule ids for persistence."""
    evaluation = template_context.get("clinical_rule_evaluation")
    if not isinstance(evaluation, dict) or not isinstance(evaluation.get("release"), dict):
        return None
    matched_rule_ids = list(
        dict.fromkeys(
            str(entry.get("rule_id"))
            for entry in (evaluation.get("trace") or [])
            if isinstance(entry, dict) and entry.get("matched") and entry.get("rule_id")
        )
    )
    return {
        "release": evaluation["release"],
        "matched_rule_ids": matched_rule_ids,
    }


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
    user: ApiUser = Depends(require_access(permission="report:preview")),
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
    html = render_report_html(
        template_name=template_name,
        template_context=template_context,
        snapshot_rows=snapshot_rows,
        analyte=report_type,
        preview=not to_bool(save, default=False),
    )
    payload = report_service.preview_payload(
        sample=sample,
        request_path=f"/api/v1/samples/{sample_id}/reports/{report_type}/preview",
        include_snapshot=include_snapshot,
        template_name=template_name,
        template_context=template_context,
        html=html,
        snapshot_rows=snapshot_rows,
    )
    return util.common.convert_to_serializable(payload)


@router.get(
    "/api/v1/samples/{sample_id}/reports/{report_type}/preview/pdf",
    response_class=Response,
    summary="Download sample report preview as PDF",
)
def preview_report_pdf(
    sample_id: str,
    report_type: ReportAnalyte,
    include_snapshot: bool = Query(default=True),
    user: ApiUser = Depends(require_access(permission="report:preview")),
):
    """Render the current temporary report preview as a PDF download."""
    sample, assay_config = _load_report_context(sample_id, user)
    _validate_report_inputs(report_type, sample, assay_config)
    template_name, template_context, snapshot_rows = _build_preview_report(
        report_type,
        sample,
        assay_config,
        save=False,
        include_snapshot=to_bool(include_snapshot, default=True),
    )
    html = render_report_html(
        template_name=template_name,
        template_context=template_context,
        snapshot_rows=snapshot_rows or [],
        analyte=report_type,
        preview=True,
    )
    filename = f"{sample.get('name') or sample_id}_{report_type}_preview.pdf"
    return Response(
        content=render_pdf_bytes(html),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/api/v1/samples/{sample_id}/reports/{report_type}",
    response_model=ReportSavePayload,
    status_code=201,
    summary="Create sample report",
)
def save_report(
    sample_id: str,
    report_type: ReportAnalyte,
    user: ApiUser = Depends(require_access(permission="report:create")),
):
    """Persist a rendered sample report."""
    sample, assay_config = _load_report_context(sample_id, user)
    _validate_report_inputs(report_type, sample, assay_config)

    report_num = _next_report_num(report_type, sample)
    report_id, report_path, report_file = _build_report_location(report_type, sample, assay_config)
    _prepare_report_output(report_type, report_path, report_file)

    template_name, template_context, snapshot_rows = _build_preview_report(
        report_type,
        sample,
        assay_config,
        save=True,
        include_snapshot=True,
    )
    template_sample = template_context.get("sample")
    if isinstance(template_sample, dict):
        template_sample["report_num"] = max(int(report_num) - 1, 0)
    snapshot_rows = snapshot_rows or []
    html = render_report_html(
        template_name=template_name,
        template_context=template_context,
        snapshot_rows=snapshot_rows,
        analyte=report_type,
        preview=False,
    )

    report_oid, pdf_file = _persist_report(
        report_type,
        sample_id=sample_id,
        sample=sample,
        report_num=report_num,
        report_id=report_id,
        report_file=report_file,
        html=html,
        snapshot_rows=snapshot_rows,
        created_by=current_username(),
        rule_provenance=_clinical_rule_provenance(template_context),
    )

    payload = report_service.save_payload(
        sample=sample,
        report_id=report_id,
        report_oid=str(report_oid),
        report_file=report_file,
        pdf_file=pdf_file,
        snapshot_rows=snapshot_rows,
    )
    response_payload = util.common.convert_to_serializable(payload)
    return response_payload
