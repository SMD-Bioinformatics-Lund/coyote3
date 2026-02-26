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
    g,
    send_from_directory,
    flash,
    jsonify,
)
from flask_login import current_user, login_required
from flask import current_app as app
from coyote.blueprints.home import home_bp
from coyote.blueprints.home.forms import SampleSearchForm
from coyote.util.decorators.access import require_sample_access
from coyote.services.auth.decorators import require
from coyote.services.audit_logs.decorators import log_action
from coyote.integrations.api.api_client import ApiRequestError, build_forward_headers, get_web_api_client
import os
import re
import json


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

    # Handle form submission for sample search
    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data
        search_mode = search_slider_values[int(form.search_mode_slider.data)]

    # Determine the search mode and status
    if not search_mode:
        search_mode = status
    else:
        status = search_mode

    try:
        payload = get_web_api_client().get_home_samples(
            status=status,
            search_str=search_str,
            search_mode=search_mode,
            panel_type=panel_type,
            panel_tech=panel_tech,
            assay_group=assay_group,
            headers=build_forward_headers(request.headers),
        )
        live_samples = payload.live_samples
        done_samples = payload.done_samples
    except ApiRequestError as exc:
        app.home_logger.error("Failed to fetch home samples via API: %s", exc)
        flash("Failed to load samples.", "red")
        live_samples = []
        done_samples = []

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


@home_bp.route("/<string:sample_id>/reports/<string:report_id>", endpoint="view_report")
@home_bp.route(
    "/<string:sample_id>/reports/<string:report_id>/download",
    endpoint="download_report",
    methods=["GET"],
)
@require("view_reports", min_role="admin")
@require_sample_access("sample_id")
@log_action(action_name="view_report", call_type="user")
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
        payload = get_web_api_client().get_home_report_context(
            sample_id=sample_id,
            report_id=report_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.home_logger.error(
            "Failed to fetch report context via API for sample %s report %s: %s",
            sample_id,
            report_id,
            exc,
        )
        flash("Failed to load report details.", "red")
        return redirect(url_for("dna_bp.home_screen"))

    filepath = payload.filepath

    if filepath:
        # Extract the directory and filename from the file path
        directory, filename = os.path.split(filepath)

        # Check if the file exists and serve it
        if os.path.exists(filepath):
            if request.endpoint == "home_bp.view_report":
                app.home_logger.info(
                    f"User {current_user.id} is viewing report {report_id} for sample {sample_id}"
                )
                # log Action
                g.audit_metadata = {
                    "sample": sample_id,
                    "report": report_id,
                    "action": "view_report",
                }
                return send_from_directory(directory, filename)
            elif request.endpoint == "home_bp.download_report":
                app.home_logger.info(
                    f"User {current_user.id} is downloading report {report_id} for sample {sample_id}"
                )
                # log Action
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
            # log Action
            g.audit_metadata = {
                "sample": sample_id,
                "report": report_id,
                "message": "No report file found",
            }
            flash("Requested report file does not exist.", "red")

    # Redirect to the home screen if the file does not exist
    return redirect(url_for("dna_bp.home_screen"))


@home_bp.route("/<string:sample_id>/edit", methods=["GET"])
@require("edit_sample", min_role="user")
@require_sample_access("sample_id")
@log_action("sample_settings", call_type="user_call")
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
        payload = get_web_api_client().get_home_edit_context(
            sample_id=sample_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        g.audit_metadata = {
            "sample": sample_id,
            "message": "No sample found",
        }
        flash("Sample not found.", "red")
        app.home_logger.error(
            "Failed to fetch edit context via API for sample %s: %s", sample_id, exc
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


@home_bp.route("/<string:sample_id>/isgls", methods=["GET"])
@require_sample_access("sample_id")
def list_isgls(sample_id: str) -> Response:
    """
    Return adhoc in-study gene lists for the sample's assay as JSON.

    Args:
        sample_id (str): The unique identifier of the sample.

    Returns:
        Response: JSON response with key `items` containing a list of objects:
            - `name` (str): gene list name
            - `genes` (list[str]): gene symbols in the list
    """
    try:
        payload = get_web_api_client().get_home_isgls(
            sample_id=sample_id,
            headers=build_forward_headers(request.headers),
        )
        return jsonify({"items": payload.items})
    except ApiRequestError as exc:
        app.home_logger.error("Failed to fetch ISGLs via API for sample %s: %s", sample_id, exc)
        return jsonify({"items": []})


@home_bp.route("/<string:sample_id>/genes/apply-isgl", methods=["POST"])
@require("edit_sample", min_role="user")
@require_sample_access("sample_id")
@log_action(action_name="apply_isgl", call_type="user")
def apply_isgl(sample_id: str) -> Response:
    """
    Apply adhoc in-study gene list to the sample's adhoc gene filter.

    Expects JSON body with:
        - `isgl_ids` (list[str]): IDs of the in-study gene lists to apply

    Args:
        sample_id (str): The unique identifier of the sample.

    Returns:
        Response: JSON response indicating success or failure.
    """

    payload = request.get_json(silent=True) or {}
    isgl_ids = payload.get("isgl_ids", [])

    if payload and (isgl_ids or isgl_ids == []):
        # log Action
        g.audit_metadata = {
            "sample": sample_id,
            "isgl_ids": isgl_ids,
        }
        try:
            get_web_api_client().apply_home_isgl(
                sample_id=sample_id,
                isgl_ids=(isgl_ids if isinstance(isgl_ids, list) else []),
                headers=build_forward_headers(request.headers),
            )
            flash(f"Gene list(s) {isgl_ids} applied to sample.", "green")
            app.home_logger.info(
                f"Applied gene list(s) {isgl_ids} to sample {sample_id} adhoc gene filter"
            )
        except ApiRequestError as exc:
            flash(f"Failed to apply gene list(s): {exc}", "red")

    return jsonify({"ok": True})


@home_bp.route("/<string:sample_id>/adhoc_genes", methods=["POST"])
@require("edit_sample", min_role="user")
@require_sample_access("sample_id")
@log_action(action_name="save_adhoc_genes", call_type="user")
def save_adhoc_genes(sample_id: str) -> Response:
    """
    Save adhoc genes to the sample's adhoc gene filter.
    Expects JSON body with:
        - `genes` (str): Comma, space, or newline-separated gene symbols
        - `label` (str, optional): Label for the adhoc gene list
    Args:
        sample_id (str): The unique identifier of the sample.
    Returns:
        Response: JSON response indicating success.
    """
    data = request.get_json()
    genes = [g.strip() for g in re.split(r"[ ,\n]+", data.get("genes", "")) if g.strip()]
    genes.sort()
    label = data.get("label") or "adhoc"
    try:
        get_web_api_client().save_home_adhoc_genes(
            sample_id=sample_id,
            genes=data.get("genes", ""),
            label=label,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        flash(f"Failed to save AdHoc genes: {exc}", "red")
        return jsonify({"ok": False}), 502
    # log Action
    g.audit_metadata = {
        "sample": sample_id,
        "label": label,
        "gene_count": len(genes),
    }
    flash("AdHoc genes saved to sample.", "green")
    app.home_logger.info(f"Saved {len(genes)} AdHoc genes to sample {sample_id} adhoc gene filter")

    return jsonify({"ok": True})


@home_bp.route("/<string:sample_id>/adhoc_genes/clear", methods=["POST"])
@require("edit_sample", min_role="user")
@require_sample_access("sample_id")
@log_action(action_name="clear_adhoc_genes", call_type="user")
def clear_adhoc_genes(sample_id: str) -> Response:
    """
    Clear adhoc genes from the sample's adhoc gene filter.
    Args:
        sample_id (str): The unique identifier of the sample.
    Returns:
        Response: JSON response indicating success.
    """
    try:
        get_web_api_client().clear_home_adhoc_genes(
            sample_id=sample_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        flash(f"Failed to clear AdHoc genes: {exc}", "red")
        return jsonify({"ok": False}), 502
    # log Action
    g.audit_metadata = {
        "sample": sample_id,
        "action": "clear_adhoc_genes",
    }
    flash("AdHoc genes cleared from sample.", "green")
    app.home_logger.info(f"Cleared AdHoc genes from sample {sample_id} adhoc gene filter")
    return jsonify({"ok": True})


@home_bp.route("/<string:sample_id>/effective-genes/all", methods=["GET"])
@require_sample_access("sample_id")
def get_effective_genes_all(sample_id: str) -> Response:
    """
    Return all effective genes for the sample as JSON.

    Args:
        sample_id (str): The unique identifier of the sample.
    Returns:
        Response: JSON response with key `items` containing a list of gene symbols. Also includes
                  `asp_covered_genes_count` indicating the total number of genes covered by the assay.
                  If no genes are found, returns an empty list.
    """
    try:
        payload = get_web_api_client().get_home_effective_genes_all(
            sample_id=sample_id,
            headers=build_forward_headers(request.headers),
        )
        return jsonify(
            {
                "items": payload.items,
                "asp_covered_genes_count": payload.asp_covered_genes_count,
            }
        )
    except ApiRequestError as exc:
        app.home_logger.error(
            "Failed to fetch effective genes via API for sample %s: %s", sample_id, exc
        )
        return jsonify({"items": [], "asp_covered_genes_count": 0})
