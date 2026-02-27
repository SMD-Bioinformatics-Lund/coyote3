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

"""Admin permission-management state/change routes (`toggle/delete`)."""

from flask import Response, abort, flash, g, redirect, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


@admin_bp.route("/permissions/<perm_id>/toggle", methods=["POST", "GET"])
@log_action(action_name="edit_permission", call_type="admin_call")
@login_required
def toggle_permission_active(perm_id: str) -> Response:
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("permissions", perm_id, "toggle"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", False))
        g.audit_metadata = {
            "permission": perm_id,
            "permission_status": "Active" if new_status else "Inactive",
        }
        flash(
            f"Permission '{perm_id}' is now {'Active' if new_status else 'Inactive'}.",
            "green",
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle permission policy: {exc}", "red")
    return redirect(url_for("admin_bp.list_permissions"))


@admin_bp.route("/permissions/<perm_id>/delete", methods=["GET"])
@log_action(action_name="delete_permission", call_type="admin_call")
@login_required
def delete_permission(perm_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            api_endpoints.admin("permissions", perm_id, "delete"),
            headers=forward_headers(),
        )
        g.audit_metadata = {"permission": perm_id}
        flash(f"Permission policy '{perm_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to delete permission policy: {exc}", "red")
    return redirect(url_for("admin_bp.list_permissions"))
