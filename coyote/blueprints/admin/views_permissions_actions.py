"""Admin permission-management state/change routes (`toggle/delete`)."""

from flask import Response, abort, flash, g, redirect, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)


@admin_bp.route("/permissions/<perm_id>/toggle", methods=["POST", "GET"])
@login_required
def toggle_permission_active(perm_id: str) -> Response:
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("permissions", perm_id, "toggle"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", True))
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
