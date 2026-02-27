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

"""Admin user-management state/change routes (`delete/toggle`)."""

from flask import Response, abort, flash, g, redirect, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


@admin_bp.route("/users/<user_id>/delete", methods=["GET"])
@log_action(action_name="delete_user", call_type="admin_call")
@login_required
def delete_user(user_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            api_endpoints.admin("users", user_id, "delete"),
            headers=forward_headers(),
        )
        g.audit_metadata = {"user": user_id}
        flash(f"User '{user_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete user: {exc}", "red")
    return redirect(url_for("admin_bp.manage_users"))


@admin_bp.route("/users/<user_id>/toggle", methods=["POST", "GET"])
@log_action(action_name="edit_user", call_type="admin_call")
@login_required
def toggle_user_active(user_id: str):
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("users", user_id, "toggle"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", False))
        g.audit_metadata = {
            "user": user_id,
            "user_status": "Active" if new_status else "Inactive",
        }
        flash(
            f"User: '{user_id}' is now {'active' if new_status else 'inactive'}.",
            "green",
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle user: {exc}", "red")
    return redirect(url_for("admin_bp.manage_users"))
