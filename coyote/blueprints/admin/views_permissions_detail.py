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

"""Admin permission-management detail routes (`edit/view`)."""

from copy import deepcopy

from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


def _apply_selected_version(
    permission: dict, selected_version: int | None, perm_id: str | None = None
):
    delta = None
    if selected_version and selected_version != permission.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(permission.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = permission["version_history"][version_index].get("delta", {})
            permission = util.admin.apply_version_delta(deepcopy(permission), delta_blob)
            delta = delta_blob
            if perm_id:
                permission["_id"] = perm_id
    return permission, delta


@admin_bp.route("/permissions/<perm_id>/edit", methods=["GET", "POST"])
@log_action(action_name="edit_permission", call_type="admin_call")
@login_required
def edit_permission(perm_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("permissions", perm_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load permission context: {exc}", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    permission = context.permission
    schema = context.schema_payload
    selected_version = request.args.get("version", type=int)
    permission, delta = _apply_selected_version(permission, selected_version, perm_id)

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            get_web_api_client().post_json(
                api_endpoints.admin("permissions", perm_id, "update"),
                headers=forward_headers(),
                json_body={"form_data": form_data},
            )
            g.audit_metadata = {"permission": perm_id}
            flash(f"Permission policy '{perm_id}' updated.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update permission policy: {exc}", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    return render_template(
        "permissions/edit_permission.html",
        schema=schema,
        permission=permission,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/permissions/<perm_id>/view", methods=["GET"])
@log_action(action_name="view_permission", call_type="admin_call")
@login_required
def view_permission(perm_id: str) -> str | Response:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("permissions", perm_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load permission context: {exc}", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    permission = context.permission
    schema = context.schema_payload
    selected_version = request.args.get("version", type=int)
    permission, delta = _apply_selected_version(permission, selected_version)

    return render_template(
        "permissions/view_permission.html",
        schema=schema,
        permission=permission,
        selected_version=selected_version or permission.get("version"),
        delta=delta,
    )
