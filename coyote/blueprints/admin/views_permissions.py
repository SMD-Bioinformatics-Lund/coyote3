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

"""Admin permission-management routes."""

from copy import deepcopy

from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user

from coyote.blueprints.admin import admin_bp
from coyote.extensions import store, util
from coyote.services.audit_logs.decorators import log_action
from coyote.services.auth.decorators import require
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@admin_bp.route("/permissions")
@require("view_permission_policy", min_role="admin", min_level=99999)
def list_permissions() -> str:
    permission_policies = store.permissions_handler.get_all_permissions(is_active=False)
    grouped = {}
    for p in permission_policies:
        grouped.setdefault(p["category"], []).append(p)
    return render_template("permissions/permissions.html", grouped_permissions=grouped)


@admin_bp.route("/permissions/new", methods=["GET", "POST"])
@require("create_permission_policy", min_role="admin", min_level=99999)
@log_action(action_name="create_permission", call_type="admin_call")
def create_permission() -> Response | str:
    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="acl_config",
        schema_category="RBAC",
        is_active=True,
    )
    if not active_schemas:
        flash("No active permission schemas found!", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)
    if not schema:
        flash("Selected schema not found!", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            payload = get_web_api_client().create_admin_permission(
                schema_id=schema["_id"],
                form_data=form_data,
                headers=build_forward_headers(request.headers),
            )
            g.audit_metadata = {"permission": payload.resource_id}
            flash(f"Permission policy '{payload.resource_id}' created.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to create permission policy: {exc}", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    return render_template(
        "permissions/create_permission.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=schema,
    )


@admin_bp.route("/permissions/<perm_id>/edit", methods=["GET", "POST"])
@require("edit_permission_policy", min_role="admin", min_level=99999)
@log_action(action_name="edit_permission", call_type="admin_call")
def edit_permission(perm_id: str) -> Response | str:
    permission = store.permissions_handler.get(perm_id)
    if not permission:
        return abort(404)

    schema = store.schema_handler.get_schema(permission.get("schema_name"))

    selected_version = request.args.get("version", type=int)
    delta = None

    if selected_version and selected_version != permission.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(permission.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = permission["version_history"][version_index].get("delta", {})
            permission = util.admin.apply_version_delta(deepcopy(permission), delta_blob)
            delta = delta_blob
            permission["_id"] = perm_id

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            get_web_api_client().update_admin_permission(
                perm_id=perm_id,
                form_data=form_data,
                headers=build_forward_headers(request.headers),
            )
            g.audit_metadata = {"permission": perm_id}
            flash(f"Permission policy '{perm_id}' updated.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update permission policy: {exc}", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    return render_template(
        "permissions/edit_permission.html",
        schema=schema,
        permission=permission,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/permissions/<perm_id>/view", methods=["GET"])
@require("view_permission_policy", min_role="admin", min_level=99999)
@log_action(action_name="view_permission", call_type="admin_call")
def view_permission(perm_id: str) -> str | Response:
    permission = store.permissions_handler.get(perm_id)
    if not permission:
        return abort(404)

    schema = store.schema_handler.get_schema(permission.get("schema_name"))

    if not schema:
        flash("Schema for this permission is missing.", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    selected_version = request.args.get("version", type=int)
    delta = None
    if selected_version and selected_version != permission.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(permission.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = permission["version_history"][version_index].get("delta", {})
            delta = delta_blob
            permission = util.admin.apply_version_delta(deepcopy(permission), delta_blob)

    return render_template(
        "permissions/view_permission.html",
        schema=schema,
        permission=permission,
        selected_version=selected_version or permission.get("version"),
        delta=delta,
    )


@admin_bp.route("/permissions/<perm_id>/toggle", methods=["POST", "GET"])
@require("edit_permission_policy", min_role="admin", min_level=99999)
@log_action(action_name="edit_permission", call_type="admin_call")
def toggle_permission_active(perm_id: str) -> Response:
    perm = store.permissions_handler.get(perm_id)
    if not perm:
        return abort(404)

    try:
        payload = get_web_api_client().toggle_admin_permission(
            perm_id=perm_id,
            headers=build_forward_headers(request.headers),
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
        flash(f"Failed to toggle permission policy: {exc}", "red")
    return redirect(url_for("admin_bp.list_permissions"))


@admin_bp.route("/permissions/<perm_id>/delete", methods=["GET"])
@require("delete_permission_policy", min_role="admin", min_level=99999)
@log_action(action_name="delete_permission", call_type="admin_call")
def delete_permission(perm_id: str) -> Response:
    perm = store.permissions_handler.get(perm_id)
    if not perm:
        return abort(404)

    try:
        get_web_api_client().delete_admin_permission(
            perm_id=perm_id,
            headers=build_forward_headers(request.headers),
        )
        g.audit_metadata = {"permission": perm_id}
        flash(f"Permission policy '{perm_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete permission policy: {exc}", "red")
    return redirect(url_for("admin_bp.list_permissions"))
