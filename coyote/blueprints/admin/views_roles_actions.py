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

"""Admin role-management state/change routes (`toggle/delete`)."""

from flask import Response, abort, flash, g, redirect, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


@admin_bp.route("/roles/<role_id>/toggle", methods=["POST", "GET"])
@log_action(action_name="edit_role", call_type="admin_call")
@login_required
def toggle_role_active(role_id: str) -> Response:
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("roles", role_id, "toggle"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", False))
        g.audit_metadata = {
            "role": role_id,
            "role_status": "Active" if new_status else "Inactive",
        }
        flash(
            f"Role '{role_id}' is now {'Active' if new_status else 'Inactive'}.",
            "green",
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle role: {exc}", "red")
    return redirect(url_for("admin_bp.list_roles"))


@admin_bp.route("/roles/<role_id>/delete", methods=["GET"])
@log_action(action_name="delete_role", call_type="admin_call")
@login_required
def delete_role(role_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            api_endpoints.admin("roles", role_id, "delete"),
            headers=forward_headers(),
        )
        g.audit_metadata = {"role": role_id}
        flash(f"Role '{role_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to delete role: {exc}", "red")
    return redirect(url_for("admin_bp.list_roles"))
