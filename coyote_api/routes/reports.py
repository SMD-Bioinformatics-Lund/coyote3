"""Report API routes for DNA and RNA."""

from fastapi import Depends, Query

from coyote.extensions import util
from coyote.services.workflow.dna_workflow import DNAWorkflowService
from coyote.services.workflow.rna_workflow import RNAWorkflowService
from coyote_api.app import (
    ApiUser,
    _api_error,
    _get_formatted_assay_config,
    _get_sample_for_api,
    _to_bool,
    app,
    flask_app,
    require_access,
)


@app.get("/api/v1/dna/samples/{sample_id}/report/preview")
def preview_dna_report(
    sample_id: str,
    include_snapshot: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="preview_report", min_role="user", min_level=9)),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    DNAWorkflowService.validate_report_inputs(flask_app.logger, sample, assay_config)

    html, snapshot_rows = DNAWorkflowService.build_report_payload(
        sample=sample,
        assay_config=assay_config,
        save=0,
        include_snapshot=_to_bool(include_snapshot, default=False),
    )
    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "meta": {
            "request_path": f"/api/v1/dna/samples/{sample_id}/report/preview",
            "include_snapshot": include_snapshot,
            "snapshot_count": len(snapshot_rows),
        },
        "report": {"html": html, "snapshot_rows": snapshot_rows if include_snapshot else []},
    }
    return util.common.convert_to_serializable(payload)


@app.get("/api/v1/rna/samples/{sample_id}/report/preview")
def preview_rna_report(
    sample_id: str,
    include_snapshot: bool = Query(default=False),
    user: ApiUser = Depends(require_access(permission="preview_report", min_role="user", min_level=9)),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    RNAWorkflowService.validate_report_inputs(flask_app.logger, sample, assay_config)

    html, snapshot_rows = RNAWorkflowService.build_report_payload(
        sample=sample,
        save=0,
        include_snapshot=_to_bool(include_snapshot, default=False),
    )
    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "meta": {
            "request_path": f"/api/v1/rna/samples/{sample_id}/report/preview",
            "include_snapshot": include_snapshot,
            "snapshot_count": len(snapshot_rows),
        },
        "report": {"html": html, "snapshot_rows": snapshot_rows if include_snapshot else []},
    }
    return util.common.convert_to_serializable(payload)


@app.post("/api/v1/dna/samples/{sample_id}/report/save")
def save_dna_report(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="create_report", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    DNAWorkflowService.validate_report_inputs(flask_app.logger, sample, assay_config)

    report_num = sample.get("report_num", 0) + 1
    report_id, report_path, report_file = DNAWorkflowService.build_report_location(
        sample=sample,
        assay_config=assay_config,
        reports_base_path=flask_app.config.get("REPORTS_BASE_PATH", "reports"),
    )
    DNAWorkflowService.prepare_report_output(report_path, report_file, logger=flask_app.logger)

    html, snapshot_rows = DNAWorkflowService.build_report_payload(
        sample=sample,
        assay_config=assay_config,
        save=1,
        include_snapshot=True,
    )
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

    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "report": {
            "id": report_id,
            "oid": str(report_oid),
            "file": report_file,
            "snapshot_count": len(snapshot_rows),
        },
        "meta": {"status": "saved"},
    }
    return util.common.convert_to_serializable(payload)


@app.post("/api/v1/rna/samples/{sample_id}/report/save")
def save_rna_report(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="create_report", min_role="admin")),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    RNAWorkflowService.validate_report_inputs(flask_app.logger, sample, assay_config)

    report_num = sample.get("report_num", 0) + 1
    report_id, report_path, report_file = RNAWorkflowService.build_report_location(
        sample=sample,
        assay_config=assay_config,
        reports_base_path=flask_app.config.get("REPORTS_BASE_PATH", "reports"),
    )
    RNAWorkflowService.prepare_report_output(report_path, report_file, logger=flask_app.logger)

    html, snapshot_rows = RNAWorkflowService.build_report_payload(
        sample=sample,
        save=1,
        include_snapshot=True,
    )
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

    payload = {
        "sample": {
            "id": str(sample.get("_id")),
            "name": sample.get("name"),
            "assay": sample.get("assay"),
            "profile": sample.get("profile"),
        },
        "report": {
            "id": report_id,
            "oid": str(report_oid),
            "file": report_file,
            "snapshot_count": len(snapshot_rows),
        },
        "meta": {"status": "saved"},
    }
    return util.common.convert_to_serializable(payload)
