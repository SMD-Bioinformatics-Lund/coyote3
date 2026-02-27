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

"""Admin user-management create routes."""

from flask import Response, flash, g, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


@admin_bp.route("/users/new", methods=["GET", "POST"])
@log_action(action_name="create_user", call_type="admin_call")
@login_required
def create_user() -> Response | str:
    try:
        selected_schema_id = request.args.get("schema_id")
        context = get_web_api_client().get_json(
            api_endpoints.admin("users", "create_context"),
            headers=forward_headers(),
            params={"schema_id": selected_schema_id} if selected_schema_id else None,
        )
    except ApiRequestError as exc:
        flash(f"Failed to load user schema context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    active_schemas = context.schemas
    schema = context.schema_payload
    role_map = context.role_map
    assay_group_map = context.assay_group_map

    if request.method == "POST":
        form_data: dict[str, str | list[str]] = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            payload = get_web_api_client().post_json(
                api_endpoints.admin("users", "create"),
                headers=forward_headers(),
                json_body={
                    "schema_id": context.selected_schema.get("_id"),
                    "form_data": form_data,
                },
            )
            g.audit_metadata = {"user": payload.resource_id}
            flash("User created successfully!", "green")
        except ApiRequestError as exc:
            flash(f"Failed to create user: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    return render_template(
        "users/user_create.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=context.selected_schema,
        assay_group_map=assay_group_map,
        role_map=role_map,
    )
