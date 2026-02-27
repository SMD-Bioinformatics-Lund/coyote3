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
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.blueprints.home.forms import SampleSearchForm
from coyote.integrations.api import endpoints as api_endpoints
from coyote.services.audit_logs.decorators import log_action
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


@admin_bp.route("/manage-samples", methods=["GET", "POST"])
@login_required
def all_samples() -> str | Response:
    form = SampleSearchForm()
    search_str = ""

    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data

    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("samples"),
            headers=forward_headers(),
            params={"search": search_str} if search_str else None,
        )
        samples = payload.samples
    except ApiRequestError as exc:
        flash(f"Failed to fetch samples: {exc}", "red")
        samples = []
    return render_template("samples/all_samples.html", all_samples=samples, form=form)


@admin_bp.route("/samples/<sample_id>/edit", methods=["GET", "POST"])
@log_action(action_name="edit_sample", call_type="developer_call")
@login_required
def edit_sample(sample_id: str) -> str | Response:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("samples", sample_id, "context"),
            headers=forward_headers(),
        )
        sample_doc = payload.sample
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("Sample not found.", "red")
        else:
            flash(f"Failed to load sample context: {exc}", "red")
        return redirect(url_for("admin_bp.all_samples"))
    sample_obj = sample_doc.pop("_id", sample_id)

    if request.method == "POST":
        json_blob = request.form.get("json_blob", "")
        try:
            updated_sample = json.loads(json_blob)
        except json.JSONDecodeError as e:
            flash(f"Invalid JSON: {e}", "red")
            return redirect(request.url)

        try:
            get_web_api_client().post_json(
                api_endpoints.admin("samples", sample_id, "update"),
                headers=forward_headers(),
                json_body={"sample": updated_sample},
            )
            flash("Sample updated successfully.", "green")
            return redirect(url_for("admin_bp.all_samples"))
        except ApiRequestError as e:
            flash(f"Error updating sample: {e}", "red")

        g.audit_metadata = {"sample_id": str(sample_obj), "sample_name": sample_id}

    return render_template("samples/sample_edit.html", sample_blob=sample_doc)


@admin_bp.route("/manage-samples/<string:sample_id>/delete", methods=["GET"])
@log_action("delete_sample", call_type="admin_call")
@login_required
def delete_sample(sample_id: str) -> Response:
    g.audit_metadata = {"sample": sample_id}
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("samples", sample_id, "delete"),
            headers=forward_headers(),
        )
        sample_name = payload.meta.get("sample_name", sample_id)
        for item in payload.meta.get("results", []):
            collection = item.get("collection", "unknown")
            if item.get("ok"):
                flash(f"Deleted {collection} for {sample_name}", "green")
            else:
                flash(f"Failed to delete {collection} for {sample_name}", "red")
    except ApiRequestError as exc:
        flash(f"Error deleting sample: {exc}", "red")
    return redirect(url_for("admin_bp.all_samples"))
