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
from flask_login import login_required
from flask import Response, flash, redirect, url_for
from coyote.blueprints.dna import dna_bp
from coyote.integrations.api.api_client import ApiRequestError
from coyote.integrations.api.web import log_api_error
from coyote.services.reporting.web_report_bridge import (
    fetch_preview_payload,
    persist_rendered_report,
    render_template_from_api_payload,
)


@dna_bp.route("/sample/<string:sample_id>/preview_report", methods=["GET", "POST"])
@login_required
def generate_dna_report(sample_id: str, **kwargs) -> Response | str:
    """
    Generate and render a preview of the DNA report for a given sample.
    """
    try:
        payload = fetch_preview_payload("dna", sample_id, include_snapshot=False, save=False)
        app.logger.info("Loaded DNA preview report from API service for sample %s", sample_id)
        return render_template_from_api_payload(payload)
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to generate DNA preview report via API for sample {sample_id}",
            flash_message="Failed to generate report preview.",
        )
        return redirect(url_for("home_bp.samples_home"))


@dna_bp.route("/sample/<string:sample_id>/report/save")
@login_required
def save_dna_report(sample_id: str) -> Response:
    """
    Generate and persist a DNA report for the specified sample.
    """
    try:
        preview_payload = fetch_preview_payload("dna", sample_id, include_snapshot=True, save=True)
        html = render_template_from_api_payload(preview_payload)
        snapshot_rows = preview_payload.report.get("snapshot_rows", [])
        payload = persist_rendered_report("dna", sample_id, html=html, snapshot_rows=snapshot_rows)
        report_id = payload.report.get("id", "unknown")
        report_file = payload.report.get("file", "unknown")
        flash(f"Report {report_id}.html has been successfully saved.", "green")
        app.logger.info("Report saved via API: %s", report_file)
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to save DNA report via API for sample {sample_id}",
            flash_message="Failed to save report.",
        )

    return redirect(url_for("home_bp.samples_home", reload=True))
