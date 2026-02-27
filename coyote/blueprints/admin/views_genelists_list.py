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

"""Admin in-silico genelist list/state routes."""

from flask import Response, abort, flash, g, redirect, render_template, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


@admin_bp.route("/genelists", methods=["GET"])
@login_required
def manage_genelists() -> str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("genelists"),
            headers=forward_headers(),
        )
        genelists = payload.genelists
    except ApiRequestError as exc:
        flash(f"Failed to fetch genelists: {exc}", "red")
        genelists = []
    return render_template("isgl/manage_isgl.html", genelists=genelists, is_public=False)


@admin_bp.route("/genelists/<genelist_id>/toggle", methods=["GET"])
@log_action(action_name="toggle_genelist", call_type="manager_call")
@login_required
def toggle_genelist(genelist_id: str) -> Response:
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("genelists", genelist_id, "toggle"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", True))
        g.audit_metadata = {
            "genelist": genelist_id,
            "genelist_status": "Active" if new_status else "Inactive",
        }
        flash(
            f"Genelist: '{genelist_id}' is now {'active' if new_status else 'inactive'}.",
            "green",
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle genelist: {exc}", "red")
    return redirect(url_for("admin_bp.manage_genelists"))


@admin_bp.route("/genelists/<genelist_id>/delete", methods=["GET"])
@log_action(action_name="delete_genelist", call_type="admin_call")
@login_required
def delete_genelist(genelist_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            api_endpoints.admin("genelists", genelist_id, "delete"),
            headers=forward_headers(),
        )
        g.audit_metadata = {"genelist": genelist_id}
        flash(f"Genelist '{genelist_id}' deleted successfully!", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete genelist: {exc}", "red")
    return redirect(url_for("admin_bp.manage_genelists"))
