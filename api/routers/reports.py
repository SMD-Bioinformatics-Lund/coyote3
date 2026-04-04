"""Canonical report router module."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Query

from api.contracts.reports import ReportPreviewPayload, ReportSavePayload
from api.core.workflows.dna_workflow import DNAWorkflowService
from api.core.workflows.rna_workflow import RNAWorkflowService
from api.extensions import store, util
from api.http import api_error as _api_error
from api.http import get_formatted_assay_config as _get_formatted_assay_config
from api.runtime_state import app as runtime_app
from api.runtime_state import current_username
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.services.reporting.report_builder import ReportAnalyte, ReportService
from api.settings import to_bool

router = APIRouter(tags=["reports"])

if not hasattr(util, "common"):
    util.init_util()


def _rna_workflow_service() -> type[RNAWorkflowService]:
    """Rna workflow service.

    Returns:
            The  rna workflow service result.
    """
    if not RNAWorkflowService.has_repository():
        RNAWorkflowService.set_repository(store.get_rna_workflow_repository())
    return RNAWorkflowService


def _dna_workflow_service() -> type[DNAWorkflowService]:
    """Dna workflow service.

    Returns:
            The  dna workflow service result.
    """
    if not DNAWorkflowService.has_repository():
        DNAWorkflowService.set_repository(store.get_dna_reporting_repository())
    return DNAWorkflowService


def _normalize_rendered_report_payload(report_payload: dict | None) -> tuple[str, list]:
    """Normalize rendered report payload.

    Args:
            report_payload: Report payload.

    Returns:
            The  normalize rendered report payload result.
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
    """Load report context.

    Args:
            sample_id: Sample id.
            user: User.

    Returns:
            The  load report context result.
    """
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    return sample, assay_config


def _validate_report_inputs(analyte: ReportAnalyte, sample: dict, assay_config: dict) -> None:
    """Validate report inputs.

    Args:
            analyte: Analyte.
            sample: Sample.
            assay_config: Assay config.

    Returns:
            None.
    """
    if analyte == "dna":
        _dna_workflow_service()
        DNAWorkflowService.validate_report_inputs(runtime_app.logger, sample, assay_config)
    else:
        _rna_workflow_service()
        RNAWorkflowService.validate_report_inputs(runtime_app.logger, sample, assay_config)


def _build_preview_report(
    analyte: ReportAnalyte, sample: dict, assay_config: dict, *, save: bool, include_snapshot: bool
):
    """Build preview report.

    Args:
            analyte: Analyte.
            sample: Sample.
            assay_config: Assay config.
            save: Save. Keyword-only argument.
            include_snapshot: Include snapshot. Keyword-only argument.

    Returns:
            The  build preview report result.
    """
    if analyte == "dna":
        _dna_workflow_service()
        return DNAWorkflowService.build_report_payload(
            sample=sample,
            assay_config=assay_config,
            save=1 if save else 0,
            include_snapshot=include_snapshot,
        )
    _rna_workflow_service()
    return RNAWorkflowService.build_report_payload(
        sample=sample,
        save=1 if save else 0,
        include_snapshot=include_snapshot,
    )


def _build_report_location(
    analyte: ReportAnalyte, sample: dict, assay_config: dict
) -> tuple[str, str, str]:
    """Build report location.

    Args:
            analyte: Analyte.
            sample: Sample.
            assay_config: Assay config.

    Returns:
            The  build report location result.
    """
    base_path = runtime_app.config.get("REPORTS_BASE_PATH", "reports")
    if analyte == "dna":
        _dna_workflow_service()
        return DNAWorkflowService.build_report_location(
            sample=sample,
            assay_config=assay_config,
            reports_base_path=base_path,
        )
    _rna_workflow_service()
    return RNAWorkflowService.build_report_location(
        sample=sample,
        assay_config=assay_config,
        reports_base_path=base_path,
    )


def _prepare_report_output(analyte: ReportAnalyte, report_path: str, report_file: str) -> None:
    """Prepare report output.

    Args:
            analyte: Analyte.
            report_path: Report path.
            report_file: Report file.

    Returns:
            None.
    """
    if analyte == "dna":
        _dna_workflow_service()
        DNAWorkflowService.prepare_report_output(
            report_path, report_file, logger=runtime_app.logger
        )
    else:
        _rna_workflow_service()
        RNAWorkflowService.prepare_report_output(
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
    """Persist report.

    Args:
            analyte: Analyte.
            sample_id: Sample id. Keyword-only argument.
            sample: Sample. Keyword-only argument.
            report_num: Report num. Keyword-only argument.
            report_id: Report id. Keyword-only argument.
            report_file: Report file. Keyword-only argument.
            html: Html. Keyword-only argument.
            snapshot_rows: Snapshot rows. Keyword-only argument.
            created_by: Created by. Keyword-only argument.

    Returns:
            The  persist report result.
    """
    if analyte == "dna":
        _dna_workflow_service()
        return DNAWorkflowService.persist_report(
            sample_id=sample_id,
            sample=sample,
            report_num=report_num,
            report_id=report_id,
            report_file=report_file,
            html=html,
            snapshot_rows=snapshot_rows,
            created_by=created_by,
        )
    _rna_workflow_service()
    return RNAWorkflowService.persist_report(
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
        require_access(permission="preview_report", min_role="user", min_level=9)
    ),
):
    """Preview report.

    Args:
        sample_id (str): Value for ``sample_id``.
        report_type (ReportAnalyte): Value for ``report_type``.
        include_snapshot (bool): Value for ``include_snapshot``.
        save (bool): Value for ``save``.
        user (ApiUser): Value for ``user``.

    Returns:
        The function result.
    """
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
    user: ApiUser = Depends(require_access(permission="create_report", min_role="admin")),
):
    """Save report.

    Args:
        sample_id (str): Value for ``sample_id``.
        report_type (ReportAnalyte): Value for ``report_type``.
        report_payload (dict | None): Value for ``report_payload``.
        user (ApiUser): Value for ``user``.

    Returns:
        The function result.
    """
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
