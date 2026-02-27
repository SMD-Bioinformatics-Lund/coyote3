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

"""Admin assay configuration list and state-change routes (`/aspc/*`)."""

from flask import Response, abort, flash, g, redirect, render_template, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


@admin_bp.route("/aspc")
@login_required
def assay_configs() -> str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("aspc"),
            headers=forward_headers(),
        )
        assay_configs = payload.assay_configs
    except ApiRequestError as exc:
        flash(f"Failed to fetch assay configs: {exc}", "red")
        assay_configs = []
    return render_template("aspc/manage_aspc.html", assay_configs=assay_configs)


@admin_bp.route("/aspc/<assay_id>/toggle", methods=["POST", "GET"])
@log_action(action_name="edit_assay_config", call_type="developer_call")
@login_required
def toggle_assay_config_active(assay_id: str) -> Response:
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("aspc", assay_id, "toggle"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", False))
        g.audit_metadata = {
            "assay": assay_id,
            "assay_status": "Active" if new_status else "Inactive",
        }
        flash(
            f"Assay config '{assay_id}' is now {'active' if new_status else 'inactive'}.",
            "green",
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle assay config: {exc}", "red")
    return redirect(url_for("admin_bp.assay_configs"))


@admin_bp.route("/aspc/<assay_id>/delete", methods=["GET"])
@log_action(action_name="delete_assay_config", call_type="admin_call")
@login_required
def delete_assay_config(assay_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            api_endpoints.admin("aspc", assay_id, "delete"),
            headers=forward_headers(),
        )
        g.audit_metadata = {"assay": assay_id}
        flash(f"Assay config '{assay_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete assay config: {exc}", "red")
    return redirect(url_for("admin_bp.assay_configs"))
