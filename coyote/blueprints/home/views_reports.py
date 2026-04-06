"""Home blueprint report read/download routes."""

from __future__ import annotations

from flask import Response, send_file
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.home import home_bp
from coyote.services.api_client.api_client import ApiRequestError
from coyote.services.api_client.home import fetch_report_path
from coyote.services.api_client.web import raise_page_load_error


def _serve_report(sample_id: str, report_id: str, *, as_attachment: bool) -> Response:
    """Resolve a report file path and serve it or raise a standard web error."""
    try:
        report_path = fetch_report_path(sample_id, report_id)
        if not str(report_path):
            raise ApiRequestError("Report file path is missing in API response")
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.home_logger,
            log_message=(
                f"Failed to resolve report path via API for sample {sample_id} report {report_id}"
            ),
            summary="Unable to load the requested report.",
            not_found_summary="The requested report was not found.",
        )

    if not report_path.exists() or not report_path.is_file():
        app.home_logger.error("Report path does not exist: %s", report_path)
        raise_page_load_error(
            ApiRequestError("Report file was not found on disk.", status_code=404),
            logger=app.home_logger,
            log_message=f"Resolved report path does not exist for sample {sample_id} report {report_id}",
            summary="Unable to open the requested report.",
            not_found_summary="The requested report file was not found.",
        )

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
