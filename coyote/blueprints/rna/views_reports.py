
"""RNA report preview/save routes."""

from flask import current_app as app
from flask_login import login_required
from flask import Response, flash, redirect, url_for

from coyote.blueprints.rna import rna_bp
from coyote.integrations.api.api_client import ApiRequestError
from coyote.integrations.api.web import log_api_error
from coyote.services.reporting.web_report_bridge import (
    render_preview_report_html,
    save_report_from_preview,
)


@rna_bp.route("/sample/<string:sample_id>/preview_report", methods=["GET", "POST"])
@rna_bp.route("/sample/preview_report/<string:sample_id>", methods=["GET", "POST"])
@login_required
def generate_rna_report(sample_id: str, **kwargs) -> Response | str:
    try:
        html = render_preview_report_html("rna", sample_id, save=False)
        app.logger.info("Loaded RNA preview report from API service for sample %s", sample_id)
        return html
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to generate RNA preview report via API for sample {sample_id}",
            flash_message="Failed to generate report preview.",
        )
        return redirect(url_for("home_bp.samples_home"))


@rna_bp.route("/sample/<string:sample_id>/report/save")
@login_required
def save_rna_report(sample_id: str) -> Response:
    try:
        payload = save_report_from_preview("rna", sample_id)
        report_id = payload.report.get("id", "unknown")
        report_file = payload.report.get("file", "unknown")
        flash(f"Report {report_id}.html has been successfully saved.", "green")
        app.logger.info("Report saved via API: %s", report_file)
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to save RNA report via API for sample {sample_id}",
            flash_message="Failed to save report.",
        )

    return redirect(url_for("home_bp.samples_home", reload=True))
