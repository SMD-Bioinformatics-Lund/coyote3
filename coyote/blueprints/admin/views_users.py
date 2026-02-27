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
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.audit_logs.decorators import log_action
from coyote.integrations.api.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@admin_bp.route("/users", methods=["GET"])
@login_required
def manage_users() -> str | Response:
    try:
        payload = get_web_api_client().get_json(
            "/api/v1/admin/users",
            headers=build_forward_headers(request.headers),
        )
        users = payload.users
        roles = payload.roles
    except ApiRequestError as exc:
        flash(f"Failed to fetch users: {exc}", "red")
        users = []
        roles = {}
    return render_template("users/manage_users.html", users=users, roles=roles)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@log_action(action_name="create_user", call_type="admin_call")
@login_required
def create_user() -> Response | str:
    try:
        selected_schema_id = request.args.get("schema_id")
        context = get_web_api_client().get_json(
            "/api/v1/admin/users/create_context",
            headers=build_forward_headers(request.headers),
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
                "/api/v1/admin/users/create",
                headers=build_forward_headers(request.headers),
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


@admin_bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@log_action("edit_user", call_type="admin_call")
@login_required
def edit_user(user_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_json(
            f"/api/v1/admin/users/{user_id}/context",
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load user context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    user_doc = context.user_doc
    schema = context.schema_payload
    role_map = context.role_map
    assay_group_map = context.assay_group_map

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
            get_web_api_client().post_json(
                f"/api/v1/admin/users/{user_id}/update",
                headers=build_forward_headers(request.headers),
                json_body={"form_data": form_data},
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
@log_action("view_user", call_type="admin_call or user_call")
@login_required
def view_user(user_id: str) -> str | Response:
    try:
        context = get_web_api_client().get_json(
            f"/api/v1/admin/users/{user_id}/context",
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("User not found.", "red")
            return redirect(url_for("admin_bp.manage_users"))
        flash(f"Failed to load user context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    user_doc = context.user_doc
    schema = context.schema_payload

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
@log_action(action_name="delete_user", call_type="admin_call")
@login_required
def delete_user(user_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/admin/users/{user_id}/delete",
            headers=build_forward_headers(request.headers),
        )
        g.audit_metadata = {"user": user_id}
        flash(f"User '{user_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete user: {exc}", "red")
    return redirect(url_for("admin_bp.manage_users"))


@admin_bp.route("/users/validate_username", methods=["POST"])
@login_required
def validate_username() -> Response:
    username = request.json.get("username").lower()
    try:
        payload = get_web_api_client().post_json(
            "/api/v1/admin/users/validate_username",
            headers=build_forward_headers(request.headers),
            json_body={"username": username},
        )
        exists = bool(payload.get("exists", False))
        return jsonify({"exists": exists})
    except ApiRequestError as exc:
        return jsonify({"exists": False, "error": str(exc)}), 502


@admin_bp.route("/users/validate_email", methods=["POST"])
@login_required
def validate_email():
    email = request.json.get("email").lower()
    try:
        payload = get_web_api_client().post_json(
            "/api/v1/admin/users/validate_email",
            headers=build_forward_headers(request.headers),
            json_body={"email": email},
        )
        exists = bool(payload.get("exists", False))
        return jsonify({"exists": exists})
    except ApiRequestError as exc:
        return jsonify({"exists": False, "error": str(exc)}), 502


@admin_bp.route("/users/<user_id>/toggle", methods=["POST", "GET"])
@log_action(action_name="edit_user", call_type="admin_call")
@login_required
def toggle_user_active(user_id: str):
    try:
        payload = get_web_api_client().post_json(
            f"/api/v1/admin/users/{user_id}/toggle",
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
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle user: {exc}", "red")
    return redirect(url_for("admin_bp.manage_users"))
