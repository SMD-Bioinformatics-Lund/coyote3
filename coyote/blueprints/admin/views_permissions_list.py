"""Admin permission-management list routes."""

from flask import flash, render_template
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)


@admin_bp.route("/permissions")
@login_required
def list_permissions() -> str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("permissions"),
            headers=forward_headers(),
        )
        grouped_permissions = payload.get("grouped_permissions", {})
    except AttributeError as exc:
        flash(f"Failed to parse permissions payload: {exc}", "red")
        grouped_permissions = {}
    except ApiRequestError as exc:
        flash(f"Failed to fetch permissions: {exc}", "red")
        grouped_permissions = {}
    return render_template("permissions/permissions.html", grouped_permissions=grouped_permissions)
