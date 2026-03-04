"""Home blueprint report read/download routes."""

from __future__ import annotations

from flask import Response, abort, redirect, send_file, url_for
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.home import home_bp
from coyote.services.api_client.api_client import ApiRequestError
from coyote.services.api_client.home import fetch_report_path
from coyote.services.api_client.web import log_api_error


def _serve_report(sample_id: str, report_id: str, *, as_attachment: bool) -> Response:
    try:
        report_path = fetch_report_path(sample_id, report_id)
        if not str(report_path):
            raise ApiRequestError("Report file path is missing in API response")
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message=(
                "Failed to resolve report path via API for "
                f"sample {sample_id} report {report_id}"
            ),
            flash_message="Failed to load report.",
        )
        return redirect(url_for("home_bp.samples_home"))

    if not report_path.exists() or not report_path.is_file():
        app.home_logger.error("Report path does not exist: %s", report_path)
        if as_attachment:
            return redirect(url_for("home_bp.samples_home"))
        abort(404)

    return send_file(report_path, as_attachment=as_attachment, download_name=report_path.name)


@home_bp.route("/<string:sample_id>/reports/<string:report_id>", methods=["GET"])
@login_required
def view_report(sample_id: str, report_id: str) -> Response:
    """Open a generated report in browser."""
    return _serve_report(sample_id, report_id, as_attachment=False)


@home_bp.route("/<string:sample_id>/reports/<string:report_id>/download", methods=["GET"])
@login_required
def download_report(sample_id: str, report_id: str) -> Response:
    """Download a generated report file."""
    return _serve_report(sample_id, report_id, as_attachment=True)
