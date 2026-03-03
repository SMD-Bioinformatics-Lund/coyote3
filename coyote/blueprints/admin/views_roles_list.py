
"""Admin role-management list routes."""

from flask import flash, render_template
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import ApiRequestError, forward_headers, get_web_api_client


@admin_bp.route("/roles")
@login_required
def list_roles() -> str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("roles"),
            headers=forward_headers(),
        )
        roles = payload.roles
    except ApiRequestError as exc:
        flash(f"Failed to fetch roles: {exc}", "red")
        roles = []
    return render_template("roles/roles.html", roles=roles)
