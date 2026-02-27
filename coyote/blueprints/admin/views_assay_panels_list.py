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

"""Admin assay panel list and state-change routes (`/asp/*`)."""

from flask import Response, abort, flash, g, redirect, render_template, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


@admin_bp.route("/asp/manage", methods=["GET"])
@login_required
def manage_assay_panels():
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("asp"),
            headers=forward_headers(),
        )
        panels = payload.panels
    except ApiRequestError as exc:
        flash(f"Failed to fetch panels: {exc}", "red")
        panels = []
    return render_template("asp/manage_asp.html", panels=panels)


@admin_bp.route("/asp/<assay_panel_id>/toggle", methods=["POST", "GET"])
@log_action(action_name="toggle_asp", call_type="manager_call")
@login_required
def toggle_assay_panel_active(assay_panel_id: str) -> Response:
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("asp", assay_panel_id, "toggle"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", False))
        g.audit_metadata = {
            "panel": assay_panel_id,
            "panel_status": "Active" if new_status else "Inactive",
        }
        flash(f"Panel '{assay_panel_id}' status toggled!", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle panel: {exc}", "red")
    return redirect(url_for("admin_bp.manage_assay_panels"))


@admin_bp.route("/asp/<assay_panel_id>/delete", methods=["GET"])
@log_action(action_name="delete_asp", call_type="admin_call")
@login_required
def delete_assay_panel(assay_panel_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            api_endpoints.admin("asp", assay_panel_id, "delete"),
            headers=forward_headers(),
        )
        g.audit_metadata = {"panel": assay_panel_id}
        flash(f"Panel '{assay_panel_id}' deleted!", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete panel: {exc}", "red")
    return redirect(url_for("admin_bp.manage_assay_panels"))
