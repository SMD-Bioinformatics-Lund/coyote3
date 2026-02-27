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

"""Home blueprint routes for sample listing and sample settings pages."""

from flask import Response, flash, g, redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.home import home_bp
from coyote.blueprints.home.forms import SampleSearchForm
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.integrations.api.web import log_api_error
from coyote.services.audit_logs.decorators import log_action


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
    reload: bool = False,
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
        reload (bool): Whether to reload the samples. Defaults to False.

    Returns:
        Response: Renders the `samples_home.html` template with the filtered samples and form data.
    """
    form = SampleSearchForm()
    search_str = ""
    search_slider_values = {1: "done", 2: "both", 3: "live"}
    search_mode = None

    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data
        search_mode = search_slider_values[int(form.search_mode_slider.data)]

    if not search_mode:
        search_mode = status
    else:
        status = search_mode

    try:
        params = {
            "status": status,
            "search_str": search_str,
            "search_mode": search_mode,
        }
        if panel_type:
            params["panel_type"] = panel_type
        if panel_tech:
            params["panel_tech"] = panel_tech
        if assay_group:
            params["assay_group"] = assay_group
        payload = get_web_api_client().get_json(
            api_endpoints.home("samples"),
            headers=forward_headers(),
            params=params,
        )
        live_samples = payload.live_samples
        done_samples = payload.done_samples
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message="Failed to fetch home samples via API",
            flash_message="Failed to load samples.",
        )
        live_samples = []
        done_samples = []

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


@home_bp.route("/<string:sample_id>/edit", methods=["GET"])
@log_action("sample_settings", call_type="user_call")
@login_required
def edit_sample(sample_id: str) -> str | Response:
    """
    Redirects to the sample edit page for the given sample ID.

    Args:
        sample_id (str): The unique identifier of the sample to edit.

    Returns:
        str | Response: Renders the `edit_sample.html` template with the sample data if found,
                  otherwise redirects to the samples home page with an error message.
    """

    try:
        payload = get_web_api_client().get_json(
            api_endpoints.home_sample(sample_id, "edit_context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        g.audit_metadata = {
            "sample": sample_id,
            "message": "No sample found",
        }
        log_api_error(
            exc,
            logger=app.home_logger,
            log_message=f"Failed to fetch edit context via API for sample {sample_id}",
            flash_message="Sample not found.",
        )
        return redirect(url_for("home_bp.samples_home"))

    sample = payload.sample
    asp = payload.asp
    variant_stats_raw = payload.variant_stats_raw
    variant_stats_filtered = payload.variant_stats_filtered

    if not sample:
        g.audit_metadata = {"sample": sample_id, "message": "No sample found"}
        flash("Sample not found.", "red")
        app.home_logger.error("Sample %s not found, redirecting to home page", sample_id)
        return redirect(url_for("home_bp.samples_home"))
    return render_template(
        "edit_sample.html",
        sample=sample,
        variant_stats_raw=variant_stats_raw,
        variant_stats_filtered=variant_stats_filtered,
        asp=asp,
    )
