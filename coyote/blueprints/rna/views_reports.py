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

"""RNA report preview/save routes."""

from flask import current_app as app
from flask_login import login_required
from flask import Response, flash, redirect, request, url_for

from coyote.blueprints.rna import rna_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


@rna_bp.route("/sample/<string:sample_id>/preview_report", methods=["GET", "POST"])
@rna_bp.route("/sample/preview_report/<string:sample_id>", methods=["GET", "POST"])
@login_required
def generate_rna_report(sample_id: str, **kwargs) -> Response | str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.rna_sample(sample_id, "report", "preview"),
            headers=forward_headers(),
        )
        app.logger.info("Loaded RNA preview report from API service for sample %s", sample_id)
        return payload.report.get("html", "")
    except ApiRequestError as exc:
        app.logger.error("Failed to generate RNA preview report via API for sample %s: %s", sample_id, exc)
        flash("Failed to generate report preview.", "red")
        return redirect(url_for("home_bp.samples_home"))


@rna_bp.route("/sample/<string:sample_id>/report/save")
@login_required
def save_rna_report(sample_id: str) -> Response:
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.rna_sample(sample_id, "report", "save"),
            headers=forward_headers(),
        )
        report_id = payload.report.get("id", "unknown")
        report_file = payload.report.get("file", "unknown")
        flash(f"Report {report_id}.html has been successfully saved.", "green")
        app.logger.info("Report saved via API: %s", report_file)
    except ApiRequestError as exc:
        flash("Failed to save report.", "red")
        app.logger.error("Failed to save RNA report via API for sample %s: %s", sample_id, exc)

    return redirect(url_for("home_bp.samples_home", reload=True))
