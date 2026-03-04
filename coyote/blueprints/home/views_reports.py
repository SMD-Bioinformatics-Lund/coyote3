"""Home blueprint report read/download routes."""

from __future__ import annotations

from pathlib import Path

from flask import Response, abort, redirect, send_file, url_for
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.home import home_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import log_api_error


def _fetch_report_path(sample_id: str, report_id: str) -> Path:
    payload = get_web_api_client().get_json(
        api_endpoints.home_sample(sample_id, "reports", report_id, "context"),
        headers=forward_headers(),
    )
    filepath = payload.get("filepath")
    if not filepath:
        raise ApiRequestError("Report file path is missing in API response")
    return Path(str(filepath))


def _serve_report(sample_id: str, report_id: str, *, as_attachment: bool) -> Response:
    try:
        report_path = _fetch_report_path(sample_id, report_id)
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


@home_bp.route("/samples/<string:sample_id>/reports/<string:report_id>", methods=["GET"])
@login_required
def view_report(sample_id: str, report_id: str) -> Response:
    """Open a generated report in browser."""
    return _serve_report(sample_id, report_id, as_attachment=False)


@home_bp.route("/samples/<string:sample_id>/reports/<string:report_id>/download", methods=["GET"])
@login_required
def download_report(sample_id: str, report_id: str) -> Response:
    """Download a generated report file."""
    return _serve_report(sample_id, report_id, as_attachment=True)
