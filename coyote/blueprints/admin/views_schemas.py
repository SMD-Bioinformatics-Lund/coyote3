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

"""Admin schema-management routes."""

import json

from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.services.audit_logs.decorators import log_action
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


@admin_bp.route("/schemas")
@login_required
def schemas() -> str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("schemas"),
            headers=forward_headers(),
        )
        schemas = payload.schemas
    except ApiRequestError as exc:
        flash(f"Failed to fetch schemas: {exc}", "red")
        schemas = []
    return render_template("schemas/schemas.html", schemas=schemas)


@admin_bp.route("/schemas/<schema_id>/toggle", methods=["POST", "GET"])
@log_action(action_name="edit_schema", call_type="developer_call")
@login_required
def toggle_schema_active(schema_id: str) -> Response:
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("schemas", schema_id, "toggle"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", False))
        g.audit_metadata = {
            "schema": schema_id,
            "schema_status": "Active" if new_status else "Inactive",
        }
        flash(
            f"Schema '{schema_id}' is now {'active' if new_status else 'inactive'}.",
            "green",
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle schema: {exc}", "red")
    return redirect(url_for("admin_bp.schemas"))


@admin_bp.route("/schemas/<schema_id>/edit", methods=["GET", "POST"])
@log_action(action_name="edit_schema", call_type="developer_call")
@login_required
def edit_schema(schema_id: str) -> str | Response:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("schemas", schema_id, "context"),
            headers=forward_headers(),
        )
        schema_doc = context.schema_payload
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load schema context: {exc}", "red")
        return redirect(url_for("admin_bp.schemas"))

    if request.method == "POST":
        json_blob = request.form.get("json_blob", "")
        try:
            updated_schema = json.loads(json_blob)
            errors = util.admin.validate_schema_structure(updated_schema)
            if errors:
                for err in errors:
                    flash(f"{err}", "red")
                return render_template("schemas/schema_edit.html", schema_blob=updated_schema)
        except json.JSONDecodeError as e:
            flash(f"Invalid JSON: {e}", "red")
            return redirect(request.url)

        try:
            get_web_api_client().post_json(
                api_endpoints.admin("schemas", schema_id, "update"),
                headers=forward_headers(),
                json_body={"schema": updated_schema},
            )
            flash("Schema updated successfully.", "green")
            return redirect(url_for("admin_bp.schemas"))
        except ApiRequestError as e:
            flash(f"Error updating schema: {e}", "red")

        g.audit_metadata = {"schema": schema_id}

    return render_template("schemas/schema_edit.html", schema_blob=schema_doc)


@admin_bp.route("/schemas/new", methods=["GET", "POST"])
@log_action(action_name="create_schema", call_type="developer_call")
@login_required
def create_schema() -> str | Response:
    if request.method == "POST":
        json_blob = request.form.get("json_blob")
        try:
            parsed_schema = json.loads(json_blob)

            errors = util.admin.validate_schema_structure(parsed_schema)
            if errors:
                for err in errors:
                    flash(f"{err}", "red")
                return render_template("schemas/schema_create.html", initial_blob=parsed_schema)

            get_web_api_client().post_json(
                api_endpoints.admin("schemas", "create"),
                headers=forward_headers(),
                json_body={"schema": parsed_schema},
            )
            flash("Schema created successfully!", "green")
            return redirect(url_for("admin_bp.schemas"))

        except ApiRequestError as e:
            flash(f"Error: {e}", "red")

        g.audit_metadata = {"schema": parsed_schema.get("schema_name")}

    initial_blob = util.admin.load_json5_template()
    return render_template("schemas/schema_create.html", initial_blob=initial_blob)


@admin_bp.route("/schemas/<schema_id>/delete", methods=["GET"])
@log_action(action_name="delete_schema", call_type="admin_call")
@login_required
def delete_schema(schema_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            api_endpoints.admin("schemas", schema_id, "delete"),
            headers=forward_headers(),
        )
        g.audit_metadata = {"schema": schema_id}
        flash(f"Schema '{schema_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to delete schema: {exc}", "red")
    return redirect(url_for("admin_bp.schemas"))
