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

"""Admin user-management routes."""

from copy import deepcopy

from flask import Response, abort, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import current_user

from coyote.blueprints.admin import admin_bp
from coyote.extensions import store, util
from coyote.services.audit_logs.decorators import log_action
from coyote.services.auth.decorators import require
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@admin_bp.route("/users", methods=["GET"])
@require("view_user", min_role="admin", min_level=99999)
def manage_users() -> str | Response:
    users = store.user_handler.get_all_users()
    roles = store.roles_handler.get_role_colors()
    return render_template("users/manage_users.html", users=users, roles=roles)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@require("create_user", min_role="admin", min_level=99999)
@log_action(action_name="create_user", call_type="admin_call")
def create_user() -> Response | str:
    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="rbac_user",
        schema_category="RBAC_user",
        is_active=True,
    )

    if not active_schemas:
        flash("No active user schemas found!", "red")
        return redirect(url_for("admin_bp.manage_users"))

    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("User schema not found!", "red")
        return redirect(url_for("admin_bp.manage_users"))

    available_roles = store.roles_handler.get_all_role_names()
    schema["fields"]["role"]["options"] = available_roles

    all_roles = store.roles_handler.get_all_roles()
    role_map = {}
    for role in all_roles:
        role_map[role["_id"]] = {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
            "level": role.get("level", 0),
        }

    permission_policies = store.permissions_handler.get_all_permissions(is_active=True)
    schema["fields"]["permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]
    schema["fields"]["deny_permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]

    assay_groups = store.asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["options"] = assay_groups

    assay_groups_panels = store.asp_handler.get_all_asps()
    assay_group_map = util.common.create_assay_group_map(assay_groups_panels)

    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

    if request.method == "POST":
        form_data: dict[str, str | list[str]] = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            payload = get_web_api_client().create_admin_user(
                schema_id=schema["_id"],
                form_data=form_data,
                headers=build_forward_headers(request.headers),
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
        selected_schema=schema,
        assay_group_map=assay_group_map,
        role_map=role_map,
    )


@admin_bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@require("edit_user", min_role="admin", min_level=99999)
@log_action("edit_user", call_type="admin_call")
def edit_user(user_id: str) -> Response | str:
    user_doc = store.user_handler.user_with_id(user_id)
    schema = store.schema_handler.get_schema(user_doc.get("schema_name"))

    available_roles = store.roles_handler.get_all_role_names()
    schema["fields"]["role"]["options"] = available_roles

    permission_policies = store.permissions_handler.get_all_permissions(is_active=True)
    schema["fields"]["permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]
    schema["fields"]["deny_permissions"]["options"] = [
        {
            "value": p["_id"],
            "label": p.get("label", p["_id"]),
            "category": p.get("category", "Uncategorized"),
        }
        for p in permission_policies
    ]

    all_roles = store.roles_handler.get_all_roles()
    role_map = {}
    for role in all_roles:
        role_map[role["_id"]] = {
            "permissions": role.get("permissions", []),
            "deny_permissions": role.get("deny_permissions", []),
            "level": role.get("level", 0),
        }

    schema["fields"]["permissions"]["default"] = user_doc.get("permissions")
    schema["fields"]["deny_permissions"]["default"] = user_doc.get("deny_permissions")

    assay_groups = store.asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["options"] = assay_groups
    schema["fields"]["assay_groups"]["default"] = user_doc.get("assay_groups", [])

    assay_groups_panels = store.asp_handler.get_all_asps()
    assay_group_map = {}

    for _assay in assay_groups_panels:
        group = _assay.get("asp_group")
        if group not in assay_group_map:
            assay_group_map[group] = []

        group_map = {
            "assay_name": _assay.get("assay_name"),
            "display_name": _assay.get("display_name"),
            "asp_category": _assay.get("asp_category"),
        }
        assay_group_map[group].append(group_map)

    schema["fields"]["assays"]["default"] = user_doc.get("assays", [])

    selected_version = request.args.get("version", type=int)
    delta = None

    if selected_version and selected_version != user_doc.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(user_doc.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = user_doc["version_history"][version_index].get("delta", {})
            user_doc = util.admin.apply_version_delta(deepcopy(user_doc), delta_blob)
            delta = delta_blob
            user_doc["_id"] = user_id

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            get_web_api_client().update_admin_user(
                user_id=user_id,
                form_data=form_data,
                headers=build_forward_headers(request.headers),
            )
            g.audit_metadata = {"user": user_id}
            flash("User updated successfully.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update user: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    return render_template(
        "users/user_edit.html",
        schema=schema,
        user=user_doc,
        assay_group_map=assay_group_map,
        role_map=role_map,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/users/<user_id>/view", methods=["GET"])
@require("view_user", min_role="admin", min_level=99999)
@log_action("view_user", call_type="admin_call or user_call")
def view_user(user_id: str) -> str | Response:
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        flash("User not found.", "red")
        return redirect(url_for("admin_bp.manage_users"))

    schema = store.schema_handler.get_schema(user_doc.get("schema_name"))
    if not schema:
        flash("Schema not found for user.", "red")
        return redirect(url_for("admin_bp.manage_users"))

    selected_version = request.args.get("version", type=int)
    delta = None
    if selected_version and selected_version != user_doc.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(user_doc.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = user_doc["version_history"][version_index].get("delta", {})
            delta = delta_blob
            user_doc = util.admin.apply_version_delta(deepcopy(user_doc), delta_blob)

    return render_template(
        "users/user_view.html",
        schema=schema,
        user=user_doc,
        selected_version=selected_version or user_doc.get("version"),
        delta=delta,
    )


@admin_bp.route("/users/<user_id>/delete", methods=["GET"])
@require("delete_user", min_role="admin", min_level=99999)
@log_action(action_name="delete_user", call_type="admin_call")
def delete_user(user_id: str) -> Response:
    try:
        get_web_api_client().delete_admin_user(
            user_id=user_id,
            headers=build_forward_headers(request.headers),
        )
        g.audit_metadata = {"user": user_id}
        flash(f"User '{user_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete user: {exc}", "red")
    return redirect(url_for("admin_bp.manage_users"))


@admin_bp.route("/users/validate_username", methods=["POST"])
@require("create_user", min_role="admin", min_level=99999)
def validate_username() -> Response:
    username = request.json.get("username").lower()
    try:
        exists = get_web_api_client().validate_admin_username(
            username=username,
            headers=build_forward_headers(request.headers),
        )
        return jsonify({"exists": exists})
    except ApiRequestError as exc:
        return jsonify({"exists": False, "error": str(exc)}), 502


@admin_bp.route("/users/validate_email", methods=["POST"])
@require("create_user", min_role="admin", min_level=99999)
def validate_email():
    email = request.json.get("email").lower()
    try:
        exists = get_web_api_client().validate_admin_email(
            email=email,
            headers=build_forward_headers(request.headers),
        )
        return jsonify({"exists": exists})
    except ApiRequestError as exc:
        return jsonify({"exists": False, "error": str(exc)}), 502


@admin_bp.route("/users/<user_id>/toggle", methods=["POST", "GET"])
@require("edit_user", min_role="admin", min_level=99999)
@log_action(action_name="edit_user", call_type="admin_call")
def toggle_user_active(user_id: str):
    user_doc = store.user_handler.user_with_id(user_id)
    if not user_doc:
        return abort(404)

    try:
        payload = get_web_api_client().toggle_admin_user(
            user_id=user_id,
            headers=build_forward_headers(request.headers),
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
        flash(f"Failed to toggle user: {exc}", "red")
    return redirect(url_for("admin_bp.manage_users"))
