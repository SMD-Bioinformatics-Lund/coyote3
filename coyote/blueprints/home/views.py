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

"""
This module defines the routes and logic for the home page and report viewing in the Coyote application.
It includes functionality for handling sample searches, filtering samples based on user access, and rendering
the appropriate templates for the user interface.
"""

from flask import (
    Response,
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
    flash,
)
from flask_login import current_user, login_required
from flask import current_app as app
from coyote.extensions import store
from coyote.blueprints.home import home_bp
from coyote.blueprints.home.forms import SampleSearchForm
from coyote.extensions import util
from coyote.util.decorators.access import require_sample_access
from coyote.services.auth.decorators import require
from coyote.util.misc import get_sample_and_assay_config
import os


@home_bp.route("/", methods=["GET", "POST"])
@home_bp.route("/<string:status>", methods=["GET", "POST"])
@home_bp.route(
    "/<string:panel_type>/<string:panel_tech>/<string:assay_group>",
    methods=["GET", "POST"],
)
@home_bp.route(
    "/<string:panel_type>/<string:panel_tech>/<string:assay_group>/<string:status>",
    methods=["GET", "POST"],
)
@login_required
def samples_home(
    panel_type: str | None = None,
    panel_tech: str | None = None,
    assay_group: str | None = None,
    status: str = "live",
):
    """
    Handles the main logic for the samples home page. This includes:
    - Searching for samples based on user input.
    - Filtering samples based on user roles, permissions, and access.
    - Displaying live and completed samples.

    Args:
        panel_type (str, Optional): The type of panel (e.g., DNA, RNA). Defaults to None.
        panel_tech (str, Optional): The technology used for the panel. Defaults to None.
        assay_group (str, Optional): The assay group to filter samples. Defaults to None.
        status (str): The status of the samples to display ('live' or 'done'). Defaults to "live".

    Returns:
        Response: Renders the `samples_home.html` template with the filtered samples and form data.
    """
    form = SampleSearchForm()
    search_str = ""
    search_slider_values = {1: "done", 2: "both", 3: "live"}
    search_mode = None

    # Handle form submission for sample search
    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data
        search_mode = search_slider_values[int(form.search_mode_slider.data)]

    limit_done_samples = 50

    # Determine the search mode and status
    if not search_mode:
        search_mode = status
    else:
        status = search_mode

    # Get user-specific environments and assays
    user_envs = current_user.envs
    user_assays = current_user.assays

    # Filter accessible assays based on the provided panel type, technology, and assay group
    if panel_type and panel_tech and assay_group:
        assay_list = (
            current_user.asp_map.get(panel_type, {}).get(panel_tech, {}).get(assay_group, [])
        )
        accessible_assays = [a for a in assay_list if a in user_assays]
    else:
        accessible_assays = user_assays

    # Fetch completed samples if the status is 'done' or 'both'
    if status == "done" or search_mode in ["done", "both"]:
        done_samples = store.sample_handler.get_samples(
            user_assays=accessible_assays,
            user_envs=user_envs,
            status=status,
            search_str=search_str,
            report=True,
            limit=limit_done_samples,
            use_cache=True,
        )
    # Fetch live samples if the status is 'live'
    elif status == "live":
        time_limit = util.common.get_date_days_ago(days=1000)
        done_samples = store.sample_handler.get_samples(
            user_assays=accessible_assays,
            status=status,
            user_envs=user_envs,
            search_str=search_str,
            report=True,
            time_limit=time_limit,
            use_cache=True,
        )
    else:
        done_samples = []

    # Fetch live samples if the status is 'live' or 'both'
    if status == "live" or search_mode in ["live", "both"]:
        live_samples = store.sample_handler.get_samples(
            user_assays=accessible_assays,
            status=status,
            user_envs=user_envs,
            search_str=search_str,
            report=False,
            use_cache=True,
        )
    else:
        live_samples = []

    for samp in done_samples:
        samp["last_report_time_created"] = (
            samp["reports"][-1]["time_created"]
            if samp.get("reports") and samp["reports"][-1].get("time_created")
            else 0
        )

    # Render the samples home page with the filtered samples and form data
    return render_template(
        "samples_home.html",
        live_samples=live_samples,
        done_samples=done_samples,
        form=form,
        assay_group=assay_group,
        panel_type=panel_type,
        panel_tech=panel_tech,
        status=status,
        search_mode=search_mode,
    )


@home_bp.route("/<string:sample_id>/reports/<string:report_id>")
@require("view_reports", min_role="admin")
@require_sample_access("sample_id")
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
    # Retrieve the report details using the sample and report IDs
    report = store.sample_handler.get_report(sample_id, report_id)
    report_name = report.get("report_name", None)
    filepath = report.get("filepath", None)

    if not filepath:
        result = get_sample_and_assay_config(sample_id)
        if isinstance(result, Response):
            return result
        sample, assay_config, assay_config_schema = result

        report_sub_dir = assay_config.get("reporting", {}).get("report_folder", "")

        filepath = f"{app.config.get('REPORTS_BASE_PATH', '')}/{report_sub_dir}/{report_name}"

    if filepath:
        # Extract the directory and filename from the file path
        directory, filename = os.path.split(filepath)

        # Check if the file exists and serve it
        if os.path.exists(filepath):
            return send_from_directory(directory, filename)
        else:
            flash("Requested report file does not exist.", "red")

    # Redirect to the home screen if the file does not exist
    return redirect(url_for("dna_bp.home_screen"))
