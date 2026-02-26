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

"""Admin sample-management routes."""

import json

from flask import Response, flash, g, redirect, render_template, request, url_for
from flask_login import current_user

from coyote.blueprints.admin import admin_bp
from coyote.blueprints.home.forms import SampleSearchForm
from coyote.extensions import store
from coyote.services.audit_logs.decorators import log_action
from coyote.services.auth.decorators import require
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@admin_bp.route("/manage-samples", methods=["GET", "POST"])
@require("view_sample_global", min_role="developer", min_level=9999)
def all_samples() -> str | Response:
    form = SampleSearchForm()
    search_str = ""

    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data

    limit_samples = None
    assays = current_user.assays
    samples = list(store.sample_handler.get_all_samples(assays, limit_samples, search_str))
    return render_template("samples/all_samples.html", all_samples=samples, form=form)


@admin_bp.route("/samples/<sample_id>/edit", methods=["GET", "POST"])
@require("edit_sample", min_role="developer", min_level=9999)
@log_action(action_name="edit_sample", call_type="developer_call")
def edit_sample(sample_id: str) -> str | Response:
    sample_doc = store.sample_handler.get_sample(sample_id)
    sample_obj = sample_doc.pop("_id")

    if request.method == "POST":
        json_blob = request.form.get("json_blob", "")
        try:
            updated_sample = json.loads(json_blob)
        except json.JSONDecodeError as e:
            flash(f"Invalid JSON: {e}", "red")
            return redirect(request.url)

        try:
            get_web_api_client().update_admin_sample(
                sample_id=sample_id,
                sample=updated_sample,
                headers=build_forward_headers(request.headers),
            )
            flash("Sample updated successfully.", "green")
            return redirect(url_for("admin_bp.all_samples"))
        except ApiRequestError as e:
            flash(f"Error updating sample: {e}", "red")

        g.audit_metadata = {"sample_id": str(sample_obj), "sample_name": sample_id}

    return render_template("samples/sample_edit.html", sample_blob=sample_doc)


@admin_bp.route("/manage-samples/<string:sample_id>/delete", methods=["GET"])
@require("delete_sample_global", min_role="developer", min_level=9999)
@log_action("delete_sample", call_type="admin_call")
def delete_sample(sample_id: str) -> Response:
    sample_name = store.sample_handler.get_sample_name(sample_id)
    g.audit_metadata = {"sample": sample_name}
    try:
        get_web_api_client().delete_admin_sample(
            sample_id=sample_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        flash(f"Error deleting sample: {exc}", "red")
    return redirect(url_for("admin_bp.all_samples"))
