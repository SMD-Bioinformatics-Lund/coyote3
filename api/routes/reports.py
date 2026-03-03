"""Report API routes for DNA and RNA."""

from fastapi import Body, Depends, Query
from typing import Any

from api.extensions import util
from api.services.workflow.dna_workflow import DNAWorkflowService
from api.services.workflow.rna_workflow import RNAWorkflowService
from api.app import (
    ApiUser,
    _api_error,
    _get_formatted_assay_config,
    _get_sample_for_api,
    _to_bool,
    app,
    require_access,
)
from api.runtime import app as runtime_app


def _sample_meta(sample: dict) -> dict:
    return {
        "id": str(sample.get("_id")),
        "name": sample.get("name"),
        "assay": sample.get("assay"),
        "profile": sample.get("profile"),
    }


def _normalize_rendered_report_payload(report_payload: dict | None) -> tuple[str, list]:
    payload = report_payload or {}
    html = payload.get("html") or ""
    snapshot_rows = payload.get("snapshot_rows") or []
    if not isinstance(html, str) or not html.strip():
        raise _api_error(400, "Missing rendered report html")
    if not isinstance(snapshot_rows, list):
        raise _api_error(400, "Invalid snapshot_rows payload")
    return html, snapshot_rows


def _preview_response_payload(
    *,
    sample: dict,
    request_path: str,
    include_snapshot: bool,
    template_name: str,
    template_context: dict[str, Any],
    snapshot_rows: list,
) -> dict:
    return {
        "sample": _sample_meta(sample),
        "meta": {
            "request_path": request_path,
            "include_snapshot": include_snapshot,
            "snapshot_count": len(snapshot_rows),
        },
        "report": {
            "template": template_name,
            "context": template_context,
            "snapshot_rows": snapshot_rows if include_snapshot else [],
        },
    }


def _save_response_payload(*, sample: dict, report_id: str, report_oid: str, report_file: str, snapshot_rows: list):
    return {
        "sample": _sample_meta(sample),
        "report": {
            "id": report_id,
            "oid": str(report_oid),
            "file": report_file,
            "snapshot_count": len(snapshot_rows),
        },
        "meta": {"status": "saved"},
    }


@app.get("/api/v1/dna/samples/{sample_id}/report/preview")
def preview_dna_report(
    sample_id: str,
    include_snapshot: bool = Query(default=False),
    save: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="preview_report", min_role="user", min_level=9)),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    DNAWorkflowService.validate_report_inputs(runtime_app.logger, sample, assay_config)

    template_name, template_context, snapshot_rows = DNAWorkflowService.build_report_payload(
        sample=sample,
        assay_config=assay_config,
        save=1 if _to_bool(save, default=False) else 0,
        include_snapshot=_to_bool(include_snapshot, default=False),
    )
    snapshot_rows = snapshot_rows or []
    payload = _preview_response_payload(
        sample=sample,
        request_path=f"/api/v1/dna/samples/{sample_id}/report/preview",
        include_snapshot=include_snapshot,
        template_name=template_name,
        template_context=template_context,
        snapshot_rows=snapshot_rows,
    )
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/rna/samples/{sample_id}/report/preview")
def preview_rna_report(
    sample_id: str,
    include_snapshot: bool = Query(default=False),
    save: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="preview_report", min_role="user", min_level=9)),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    RNAWorkflowService.validate_report_inputs(runtime_app.logger, sample, assay_config)

    template_name, template_context, snapshot_rows = RNAWorkflowService.build_report_payload(
        sample=sample,
        save=1 if _to_bool(save, default=False) else 0,
        include_snapshot=_to_bool(include_snapshot, default=False),
    )
    payload = _preview_response_payload(
        sample=sample,
        request_path=f"/api/v1/rna/samples/{sample_id}/report/preview",
        include_snapshot=include_snapshot,
        template_name=template_name,
        template_context=template_context,
        snapshot_rows=snapshot_rows,
    )
    return util.common.convert_to_serializable(payload)


@app.post("/api/v1/dna/samples/{sample_id}/report/save")
def save_dna_report(
    sample_id: str,
    report_payload: dict | None = Body(default=None),
    user: ApiUser = Depends(require_access(permission="create_report", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    DNAWorkflowService.validate_report_inputs(runtime_app.logger, sample, assay_config)

    report_num = sample.get("report_num", 0) + 1
    report_id, report_path, report_file = DNAWorkflowService.build_report_location(
        sample=sample,
        assay_config=assay_config,
        reports_base_path=runtime_app.config.get("REPORTS_BASE_PATH", "reports"),
    )
    DNAWorkflowService.prepare_report_output(report_path, report_file, logger=runtime_app.logger)

    html, snapshot_rows = _normalize_rendered_report_payload(report_payload)

    report_oid = DNAWorkflowService.persist_report(
        sample_id=sample_id,
        sample=sample,
        report_num=report_num,
        report_id=report_id,
        report_file=report_file,
        html=html,
        snapshot_rows=snapshot_rows,
        created_by=user.username,
    )

    payload = _save_response_payload(
        sample=sample,
        report_id=report_id,
        report_oid=str(report_oid),
        report_file=report_file,
        snapshot_rows=snapshot_rows,
    )
    return util.common.convert_to_serializable(payload)


@app.post("/api/v1/rna/samples/{sample_id}/report/save")
def save_rna_report(
    sample_id: str,
    report_payload: dict | None = Body(default=None),
    user: ApiUser = Depends(require_access(permission="create_report", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    RNAWorkflowService.validate_report_inputs(runtime_app.logger, sample, assay_config)

    report_num = sample.get("report_num", 0) + 1
    report_id, report_path, report_file = RNAWorkflowService.build_report_location(
        sample=sample,
        assay_config=assay_config,
        reports_base_path=runtime_app.config.get("REPORTS_BASE_PATH", "reports"),
    )
    RNAWorkflowService.prepare_report_output(report_path, report_file, logger=runtime_app.logger)

    html, snapshot_rows = _normalize_rendered_report_payload(report_payload)

    report_oid = RNAWorkflowService.persist_report(
        sample_id=sample_id,
        sample=sample,
        report_num=report_num,
        report_id=report_id,
        report_file=report_file,
        html=html,
        snapshot_rows=snapshot_rows,
        created_by=user.username,
    )

    payload = _save_response_payload(
        sample=sample,
        report_id=report_id,
        report_oid=str(report_oid),
        report_file=report_file,
        snapshot_rows=snapshot_rows,
    )
    return util.common.convert_to_serializable(payload)
