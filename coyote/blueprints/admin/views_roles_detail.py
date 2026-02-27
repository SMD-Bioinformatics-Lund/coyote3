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

"""Admin role-management detail routes (`edit/view`)."""

from copy import deepcopy

from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


def _apply_selected_version(role: dict, selected_version: int | None, role_id: str | None = None):
    delta = None
    if selected_version and selected_version != role.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(role.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = role["version_history"][version_index].get("delta", {})
            role = util.admin.apply_version_delta(deepcopy(role), delta_blob)
            delta = delta_blob
            if role_id:
                role["_id"] = role_id
    return role, delta


@admin_bp.route("/roles/<role_id>/edit", methods=["GET", "POST"])
@log_action(action_name="edit_role", call_type="admin_call")
@login_required
def edit_role(role_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("roles", role_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load role context: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

    role = context.role
    schema = context.schema_payload
    selected_version = request.args.get("version", type=int)
    role, delta = _apply_selected_version(role, selected_version, role_id)

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            get_web_api_client().post_json(
                api_endpoints.admin("roles", role_id, "update"),
                headers=forward_headers(),
                json_body={"form_data": form_data},
            )
            g.audit_metadata = {"role": role_id}
            flash(f"Role '{role_id}' updated successfully.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update role: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

    return render_template(
        "roles/edit_role.html",
        schema=schema,
        role_doc=role,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/roles/<role_id>/view", methods=["GET"])
@log_action(action_name="view_role", call_type="admin_call")
@login_required
def view_role(role_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("roles", role_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load role context: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

    role = context.role
    schema = context.schema_payload
    selected_version = request.args.get("version", type=int)
    role, delta = _apply_selected_version(role, selected_version)

    return render_template(
        "roles/view_role.html",
        schema=schema,
        role_doc=role,
        selected_version=selected_version or role.get("version"),
        delta=delta,
    )
