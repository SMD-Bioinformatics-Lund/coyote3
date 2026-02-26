#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""DNA report route handlers."""

from flask import current_app as app
from flask_login import current_user
from flask import Response, flash, redirect, request, url_for
from coyote.blueprints.dna import dna_bp
from coyote.errors.exceptions import AppError
from coyote.util.decorators.access import require_sample_access
from coyote.util.misc import get_sample_and_assay_config
from coyote.services.auth.decorators import require
from coyote.services.workflow.dna_workflow import DNAWorkflowService
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@dna_bp.route("/sample/<string:sample_id>/preview_report", methods=["GET", "POST"])
@require_sample_access("sample_id")
@require("preview_report", min_role="user", min_level=9)
def generate_dna_report(sample_id: str, **kwargs) -> Response | str:
    """
    Generate and render a preview of the DNA report for a given sample.
    """
    try:
        payload = get_web_api_client().get_dna_report_preview(
            sample_id=sample_id,
            headers=build_forward_headers(request.headers),
        )
        app.logger.info("Loaded DNA preview report from API service for sample %s", sample_id)
        return payload.report.get("html", "")
    except ApiRequestError as exc:
        app.logger.error("Failed to generate DNA preview report via API for sample %s: %s", sample_id, exc)
        flash("Failed to generate report preview.", "red")
        return redirect(url_for("home_bp.samples_home"))


@dna_bp.route("/sample/<string:sample_id>/report/save")
@require_sample_access("sample_id")
@require("create_report", min_role="admin")
def save_dna_report(sample_id: str) -> Response:
    """
    Generate and persist a DNA report for the specified sample.
    """
    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    report_num: int = sample.get("report_num", 0) + 1

    report_id, report_path, report_file = DNAWorkflowService.build_report_location(
        sample=sample,
        assay_config=assay_config,
        reports_base_path=app.config.get("REPORTS_BASE_PATH", "reports"),
    )
    DNAWorkflowService.prepare_report_output(report_path, report_file, logger=app.logger)

    try:
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
            created_by=current_user.username,
        )

        flash(f"Report {report_id}.html has been successfully saved.", "green")
        app.logger.info(f"Report saved: {report_file}")
    except AppError as app_err:
        flash(app_err.message, "red")
        app.logger.error(f"AppError: {app_err.message} | Details: {app_err.details}")
    except Exception as exc:
        flash("An unexpected error occurred while saving the report.", "red")
        app.logger.exception(f"Unexpected error: {exc}")

    return redirect(url_for("home_bp.samples_home", reload=True))
