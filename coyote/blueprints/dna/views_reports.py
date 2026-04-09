"""DNA report route handlers."""

from flask import Response, redirect, url_for
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.dna import dna_bp
from coyote.services.api_client.api_client import ApiRequestError
from coyote.services.api_client.reports import (
    fetch_preview_payload,
    render_preview_html,
    save_report_from_preview,
)
from coyote.services.api_client.web import flash_api_success, log_api_error


@dna_bp.route("/sample/<string:sample_id>/reports/preview", methods=["GET", "POST"])
@login_required
def generate_dna_report(sample_id: str, **kwargs) -> Response | str:
    """
    Generate and render a preview of the DNA report for a given sample.
    """
    try:
        payload = fetch_preview_payload("dna", sample_id, include_snapshot=False, save=False)
        html = render_preview_html(payload)
        app.logger.info("Loaded DNA preview report from API service for sample %s", sample_id)
        return html
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to generate DNA preview report via API for sample {sample_id}",
            flash_message="Failed to generate report preview.",
        )
        return redirect(url_for("home_bp.samples_home"))


@dna_bp.route("/sample/<string:sample_id>/reports/save")
@login_required
def save_dna_report(sample_id: str) -> Response:
    """
    Generate and persist a DNA report for the specified sample.
    """
    try:
        payload = save_report_from_preview("dna", sample_id)
        report_id = payload.report.get("id", "unknown")
        report_file = payload.report.get("file", "unknown")
        flash_api_success(f"Report {report_id}.html has been successfully saved.")
        app.logger.info("Report saved via API: %s", report_file)
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to save DNA report via API for sample {sample_id}",
            flash_message="Failed to save report.",
        )

    return redirect(url_for("home_bp.samples_home", reload=True))
