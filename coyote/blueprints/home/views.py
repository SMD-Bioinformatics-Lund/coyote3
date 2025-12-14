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

from copy import deepcopy
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
from coyote.extensions import store
from coyote.blueprints.home import home_bp, filters
from coyote.blueprints.home.forms import SampleSearchForm
from coyote.extensions import util
from coyote.util.decorators.access import require_sample_access
from coyote.services.auth.decorators import require
from coyote.util.misc import get_sample_and_assay_config
from coyote.services.audit_logs.decorators import log_action
import os
import re
import json
from typing import Any


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
            reload=reload,
        )
        app.home_logger.info(
            f"Searching samples with search string '{search_str}', status '{status}', "
            f"from assays '{accessible_assays}', report '{True}', limit '{limit_done_samples}', "
            f"using cache '{True}', reload is set to {reload}."
        )
    # Fetch live samples if the status is 'live'
    elif status == "live":
        time_limit = util.common.get_date_days_ago(days=90)
        done_samples = store.sample_handler.get_samples(
            user_assays=accessible_assays,
            status=status,
            user_envs=user_envs,
            search_str=search_str,
            report=True,
            time_limit=time_limit,
            use_cache=True,
            reload=reload,
        )
        app.home_logger.info(
            f"Searching samples with search string '{search_str}', status '{status}', "
            f"from assays '{accessible_assays}', report '{True}', time limit '{time_limit}', "
            f"using cache '{True}', reload is set to {reload}."
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
            reload=reload,
        )
        app.home_logger.info(
            f"Searching samples with search string '{search_str}', status '{status}', "
            f"from assays '{accessible_assays}', report '{False}', using cache '{True}', "
            f"reload is set to {reload}."
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


@home_bp.route("/<string:sample_id>/reports/<string:report_id>", endpoint="view_report")
@home_bp.get("/<string:sample_id>/reports/<string:report_id>/download", endpoint="download_report")
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
    # Retrieve the report details using the sample and report IDs
    report = store.sample_handler.get_report(sample_id, report_id)
    report_name = report.get("report_name", None)
    filepath = report.get("filepath", None)

    if not filepath:
        app.home_logger.info(f"No filepath found for report {report_id} of sample {sample_id}")
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

    # Retrieve the sample and its associated assay configuration
    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    asp = store.asp_handler.get_asp(sample.get("assay"))
    asp_group = asp.get("asp_group")
    print(asp_group)

    # If the sample has no filters set, initialize them with the assay's default filters
    if sample.get("filters") is None:
        # log Action
        g.audit_metadata = {
            "sample": sample_id,
            "message": "sample filters reset to assay defaults",
        }
        store.sample_handler.reset_sample_settings(sample["_id"], assay_config.get("filters"))
        app.home_logger.info(
            f"Sample {sample_id} filters were None, resetting to assay default filters"
        )

    # Retrieve the sample details after potential update
    sample = store.sample_handler.get_sample(sample_id)

    genes_plus_asp_genes = get_effective_genes_all(sample_id=sample_id)
    genes = genes_plus_asp_genes.get_json().get("items", [])
    asp_covered_genes_count = genes_plus_asp_genes.get_json().get("asp_covered_genes_count", 0)

    # Get variant stats for the sample without any gene filter
    variant_stats_raw = store.variant_handler.get_variant_stats(str(sample.get("_id")))

    # Get variant stats for the sample with the effective gene filter applied
    if (
        genes
        and variant_stats_raw
        and (len(genes) < asp_covered_genes_count or asp_group in ["tumwgs", "wts"])
    ):
        variant_stats_filtered = store.variant_handler.get_variant_stats(
            str(sample.get("_id")), genes=genes
        )
    else:
        variant_stats_filtered = deepcopy(variant_stats_raw)

    if not sample:
        # log Action
        g.audit_metadata = {
            "sample": sample_id,
            "message": "No sample found",
        }
        flash("Sample not found.", "red")
        app.home_logger.error(f"Sample {sample_id} not found, redirecting to home page")
        return redirect(url_for("home_bp.samples_home"))
    return render_template(
        "edit_sample.html",
        sample=sample,
        variant_stats_raw=variant_stats_raw,
        variant_stats_filtered=variant_stats_filtered,
        asp=asp,
    )


@home_bp.get("/<string:sample_id>/isgls", endpoint="isgls")
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
    sample = store.sample_handler.get_sample(sample_id)

    query = {"asp_name": sample.get("assay"), "is_active": True}

    isgls = store.isgl_handler.get_isgl_by_asp(**query)

    items: list[dict[str, Any]] = [
        {
            "_id": str(gl["_id"]),
            "name": gl["displayname"],
            "version": gl.get("version"),
            "adhoc": gl.get("adhoc", False),
            "gene_count": gl.get("gene_count", []),
        }
        for gl in isgls
    ]
    return jsonify({"items": items})


@home_bp.post("/<string:sample_id>/genes/apply-isgl", endpoint="isgl_genes")
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
    sample = store.sample_handler.get_sample(sample_id)
    filters = sample.get("filters", {})
    genelists = set(filters.get("genelists", []))
    isgl_ids = payload.get("isgl_ids", [])
    if isinstance(isgl_ids, list):
        genelists = deepcopy(isgl_ids)
    filters["genelists"] = list(genelists)

    if payload and (isgl_ids or isgl_ids == []):
        # log Action
        g.audit_metadata = {
            "sample": sample_id,
            "isgl_ids": isgl_ids,
        }
        store.sample_handler.update_sample_filters(sample.get("_id"), filters)
        flash(f"Gene list(s) {isgl_ids} applied to sample.", "green")
        app.home_logger.info(
            f"Applied gene list(s) {isgl_ids} to sample {sample_id} adhoc gene filter"
        )

    return jsonify({"ok": True})


@home_bp.post("/<string:sample_id>/adhoc_genes")
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

    sample = store.sample_handler.get_sample(sample_id)
    filters = sample.get("filters", {})
    filters["adhoc_genes"] = {"label": label, "genes": genes}
    store.sample_handler.update_sample_filters(sample.get("_id"), filters)
    # log Action
    g.audit_metadata = {
        "sample": sample_id,
        "label": label,
        "gene_count": len(genes),
    }
    flash("AdHoc genes saved to sample.", "green")
    app.home_logger.info(f"Saved {len(genes)} AdHoc genes to sample {sample_id} adhoc gene filter")

    return jsonify({"ok": True})


@home_bp.post("/<string:sample_id>/adhoc_genes/clear")
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
    sample = store.sample_handler.get_sample(sample_id)
    filters = sample.get("filters", {})
    filters.pop("adhoc_genes")
    store.sample_handler.update_sample_filters(sample.get("_id"), filters)
    # log Action
    g.audit_metadata = {
        "sample": sample_id,
        "action": "clear_adhoc_genes",
    }
    flash("AdHoc genes cleared from sample.", "green")
    app.home_logger.info(f"Cleared AdHoc genes from sample {sample_id} adhoc gene filter")
    return jsonify({"ok": True})


@home_bp.get("/<string:sample_id>/effective-genes/all")
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
    sample = store.sample_handler.get_sample(sample_id)
    if not sample:
        return jsonify({"items": []})

    filters = sample.get("filters", {})
    assay = sample.get("assay")
    asp = store.asp_handler.get_asp(assay)
    asp_group = asp.get("asp_group")
    asp_covered_genes, asp_germline_genes = store.asp_handler.get_asp_genes(assay)

    effective_genes = set(asp_covered_genes)

    adhoc_genes = set(filters.get("adhoc_genes", {}).get("genes", []))
    isgl_genes = set()

    genelists = filters.get("genelists", [])
    if genelists:
        isgls = store.isgl_handler.get_isgl_by_ids(genelists)
        for gl_key, gl_values in isgls.items():
            isgl_genes.update(gl_values.get("genes", []))

    # Combine adhoc_genes and isgl_genes if present
    filter_genes = adhoc_genes.union(isgl_genes) if adhoc_genes or isgl_genes else set()

    if filter_genes and asp_group not in ["tumwgs", "wts"]:
        effective_genes = effective_genes.intersection(filter_genes)
    elif filter_genes:
        effective_genes = deepcopy(filter_genes)

    items = sorted(effective_genes)
    return jsonify({"items": items, "asp_covered_genes_count": len(asp_covered_genes)})
