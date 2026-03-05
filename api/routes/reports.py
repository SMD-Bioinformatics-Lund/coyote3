"""Report API routes for DNA and RNA."""

from fastapi import Body, Depends, Query
from typing import Any, Literal

from api.contracts.reports import ReportPreviewPayload, ReportSavePayload
from api.extensions import util
from api.core.workflows.dna_workflow import DNAWorkflowService
from api.core.workflows.rna_workflow import RNAWorkflowService
from api.app import _api_error, _get_formatted_assay_config, app
from api.security.access import ApiUser, _get_sample_for_api, require_access
from api.runtime import app as runtime_app, current_username
from api.settings import to_bool

ReportAnalyte = Literal["dna", "rna"]


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
    snapshot_rows = payload.get("snapshot_rows")
    if snapshot_rows is None:
        snapshot_rows = []
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


def _load_report_context(sample_id: str, user: ApiUser) -> tuple[dict, dict]:
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    return sample, assay_config


def _validate_report_inputs(analyte: ReportAnalyte, sample: dict, assay_config: dict) -> None:
    if analyte == "dna":
        DNAWorkflowService.validate_report_inputs(runtime_app.logger, sample, assay_config)
    else:
        RNAWorkflowService.validate_report_inputs(runtime_app.logger, sample, assay_config)


def _build_preview_report(analyte: ReportAnalyte, sample: dict, assay_config: dict, *, save: bool, include_snapshot: bool):
    if analyte == "dna":
        return DNAWorkflowService.build_report_payload(
            sample=sample,
            assay_config=assay_config,
            save=1 if save else 0,
            include_snapshot=include_snapshot,
        )
    return RNAWorkflowService.build_report_payload(
        sample=sample,
        save=1 if save else 0,
        include_snapshot=include_snapshot,
    )


def _build_report_location(analyte: ReportAnalyte, sample: dict, assay_config: dict) -> tuple[str, str, str]:
    base_path = runtime_app.config.get("REPORTS_BASE_PATH", "reports")
    if analyte == "dna":
        return DNAWorkflowService.build_report_location(
            sample=sample,
            assay_config=assay_config,
            reports_base_path=base_path,
        )
    return RNAWorkflowService.build_report_location(
        sample=sample,
        assay_config=assay_config,
        reports_base_path=base_path,
    )


def _prepare_report_output(analyte: ReportAnalyte, report_path: str, report_file: str) -> None:
    if analyte == "dna":
        DNAWorkflowService.prepare_report_output(report_path, report_file, logger=runtime_app.logger)
    else:
        RNAWorkflowService.prepare_report_output(report_path, report_file, logger=runtime_app.logger)


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
    if analyte == "dna":
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


@app.get("/api/v1/dna/samples/{sample_id}/report/preview", response_model=ReportPreviewPayload)
def preview_dna_report(
    sample_id: str,
    include_snapshot: bool = Query(default=False),
    save: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="preview_report", min_role="user", min_level=9)),
):
    sample, assay_config = _load_report_context(sample_id, user)
    _validate_report_inputs("dna", sample, assay_config)

    template_name, template_context, snapshot_rows = _build_preview_report(
        "dna",
        sample,
        assay_config,
        save=to_bool(save, default=False),
        include_snapshot=to_bool(include_snapshot, default=False),
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


@app.get("/api/v1/rna/samples/{sample_id}/report/preview", response_model=ReportPreviewPayload)
def preview_rna_report(
    sample_id: str,
    include_snapshot: bool = Query(default=False),
    save: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="preview_report", min_role="user", min_level=9)),
):
    sample, assay_config = _load_report_context(sample_id, user)
    _validate_report_inputs("rna", sample, assay_config)

    template_name, template_context, snapshot_rows = _build_preview_report(
        "rna",
        sample,
        assay_config,
        save=to_bool(save, default=False),
        include_snapshot=to_bool(include_snapshot, default=False),
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


@app.post("/api/v1/dna/samples/{sample_id}/report/save", response_model=ReportSavePayload)
def save_dna_report(
    sample_id: str,
    report_payload: dict | None = Body(default=None),
    user: ApiUser = Depends(require_access(permission="create_report", min_role="admin")),
):
    sample, assay_config = _load_report_context(sample_id, user)
    _validate_report_inputs("dna", sample, assay_config)

    report_num = sample.get("report_num", 0) + 1
    report_id, report_path, report_file = _build_report_location("dna", sample, assay_config)
    _prepare_report_output("dna", report_path, report_file)

    html, snapshot_rows = _normalize_rendered_report_payload(report_payload)

    report_oid = _persist_report(
        "dna",
        sample_id=sample_id,
        sample=sample,
        report_num=report_num,
        report_id=report_id,
        report_file=report_file,
        html=html,
        snapshot_rows=snapshot_rows,
        created_by=current_username(),
    )

    payload = _save_response_payload(
        sample=sample,
        report_id=report_id,
        report_oid=str(report_oid),
        report_file=report_file,
        snapshot_rows=snapshot_rows,
    )
    return util.common.convert_to_serializable(payload)


@app.post("/api/v1/rna/samples/{sample_id}/report/save", response_model=ReportSavePayload)
def save_rna_report(
    sample_id: str,
    report_payload: dict | None = Body(default=None),
    user: ApiUser = Depends(require_access(permission="create_report", min_role="admin")),
):
    sample, assay_config = _load_report_context(sample_id, user)
    _validate_report_inputs("rna", sample, assay_config)

    report_num = sample.get("report_num", 0) + 1
    report_id, report_path, report_file = _build_report_location("rna", sample, assay_config)
    _prepare_report_output("rna", report_path, report_file)

    html, snapshot_rows = _normalize_rendered_report_payload(report_payload)

    report_oid = _persist_report(
        "rna",
        sample_id=sample_id,
        sample=sample,
        report_num=report_num,
        report_id=report_id,
        report_file=report_file,
        html=html,
        snapshot_rows=snapshot_rows,
        created_by=current_username(),
    )

    payload = _save_response_payload(
        sample=sample,
        report_id=report_id,
        report_oid=str(report_oid),
        report_file=report_file,
        snapshot_rows=snapshot_rows,
    )
    return util.common.convert_to_serializable(payload)
