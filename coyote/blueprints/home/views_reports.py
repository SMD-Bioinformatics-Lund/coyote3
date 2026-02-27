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

"""Home blueprint routes related to report rendering and download."""

import os

from flask import Response, flash, g, redirect, request, send_from_directory, url_for
from flask import current_app as app
from flask_login import current_user, login_required

from coyote.blueprints.home import home_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.integrations.api.web import log_api_error
from coyote.services.audit_logs.decorators import log_action


@home_bp.route("/<string:sample_id>/reports/<string:report_id>", endpoint="view_report")
@home_bp.route(
    "/<string:sample_id>/reports/<string:report_id>/download",
    endpoint="download_report",
    methods=["GET"],
)
@log_action(action_name="view_report", call_type="user")
@login_required
def view_report(sample_id: str, report_id: str) -> str | Response:
    """
    View a saved report or serve a report file for a given sample.

    This function retrieves the report details using the provided sample and report IDs.
    If the report file exists, it is served to the user. If not, the user is redirected
    to the home screen with an error message.

    Args:
        sample_id (str): The unique identifier of the sample associated with the report.
        report_id (str): The unique identifier of the report to view.

    Returns:
        Response: The report file if it exists, otherwise a redirect response to the home screen.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.home_sample(sample_id, "reports", report_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message=f"Failed to fetch report context via API for sample {sample_id} report {report_id}",
            flash_message="Failed to load report details.",
        )
        return redirect(url_for("home_bp.samples_home"))

    filepath = payload.filepath

    if filepath:
        directory, filename = os.path.split(filepath)

        if os.path.exists(filepath):
            if request.endpoint == "home_bp.view_report":
                app.home_logger.info(
                    f"User {current_user.id} is viewing report {report_id} for sample {sample_id}"
                )
                g.audit_metadata = {
                    "sample": sample_id,
                    "report": report_id,
                    "action": "view_report",
                }
                return send_from_directory(directory, filename)
            if request.endpoint == "home_bp.download_report":
                app.home_logger.info(
                    f"User {current_user.id} is downloading report {report_id} for sample {sample_id}"
                )
                g.audit_metadata = {
                    "sample": sample_id,
                    "report": report_id,
                    "action": "download_report",
                }
                return send_from_directory(directory, filename, as_attachment=True)
        else:
            app.home_logger.warning(
                f"Report file {filepath} for report {report_id} of sample {sample_id} does not exist"
            )
            g.audit_metadata = {
                "sample": sample_id,
                "report": report_id,
                "message": "No report file found",
            }
            flash("Requested report file does not exist.", "red")

    return redirect(url_for("home_bp.samples_home"))
