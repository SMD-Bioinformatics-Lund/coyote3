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

"""Admin user-management detail routes (`edit/view`)."""

from copy import deepcopy

from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


def _apply_selected_version(user_doc: dict, selected_version: int | None, user_id: str | None = None):
    delta = None
    if selected_version and selected_version != user_doc.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(user_doc.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = user_doc["version_history"][version_index].get("delta", {})
            user_doc = util.admin.apply_version_delta(deepcopy(user_doc), delta_blob)
            delta = delta_blob
            if user_id:
                user_doc["_id"] = user_id
    return user_doc, delta


@admin_bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@log_action("edit_user", call_type="admin_call")
@login_required
def edit_user(user_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("users", user_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load user context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    user_doc = context.user_doc
    schema = context.schema_payload
    role_map = context.role_map
    assay_group_map = context.assay_group_map

    selected_version = request.args.get("version", type=int)
    user_doc, delta = _apply_selected_version(user_doc, selected_version, user_id)

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            get_web_api_client().post_json(
                api_endpoints.admin("users", user_id, "update"),
                headers=forward_headers(),
                json_body={"form_data": form_data},
            )
            g.audit_metadata = {"user": user_id}
            flash("User updated successfully.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update user: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    return render_template(
        "users/user_edit.html",
        schema=schema,
        user=user_doc,
        assay_group_map=assay_group_map,
        role_map=role_map,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/users/<user_id>/view", methods=["GET"])
@log_action("view_user", call_type="admin_call or user_call")
@login_required
def view_user(user_id: str) -> str | Response:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("users", user_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("User not found.", "red")
            return redirect(url_for("admin_bp.manage_users"))
        flash(f"Failed to load user context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    user_doc = context.user_doc
    schema = context.schema_payload

    selected_version = request.args.get("version", type=int)
    user_doc, delta = _apply_selected_version(user_doc, selected_version)

    return render_template(
        "users/user_view.html",
        schema=schema,
        user=user_doc,
        selected_version=selected_version or user_doc.get("version"),
        delta=delta,
    )
