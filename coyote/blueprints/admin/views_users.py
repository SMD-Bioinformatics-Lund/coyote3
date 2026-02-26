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

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.audit_logs.decorators import log_action
from coyote.services.auth.decorators import require
from coyote.web_api.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@admin_bp.route("/users", methods=["GET"])
@require("view_user", min_role="admin", min_level=99999)
def manage_users() -> str | Response:
    try:
        payload = get_web_api_client().get_admin_users(headers=build_forward_headers(request.headers))
        users = payload.users
        roles = payload.roles
    except ApiRequestError as exc:
        flash(f"Failed to fetch users: {exc}", "red")
        users = []
        roles = {}
    return render_template("users/manage_users.html", users=users, roles=roles)


@admin_bp.route("/users/new", methods=["GET", "POST"])
@require("create_user", min_role="admin", min_level=99999)
@log_action(action_name="create_user", call_type="admin_call")
def create_user() -> Response | str:
    try:
        context = get_web_api_client().get_admin_user_create_context(
            schema_id=request.args.get("schema_id"),
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        flash(f"Failed to load user schema context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    active_schemas = context.schemas
    schema = context.schema
    role_map = context.role_map
    assay_group_map = context.assay_group_map

    if request.method == "POST":
        form_data: dict[str, str | list[str]] = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            payload = get_web_api_client().create_admin_user(
                schema_id=context.selected_schema.get("_id"),
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
        selected_schema=context.selected_schema,
        assay_group_map=assay_group_map,
        role_map=role_map,
    )


@admin_bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@require("edit_user", min_role="admin", min_level=99999)
@log_action("edit_user", call_type="admin_call")
def edit_user(user_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_admin_user_context(
            user_id=user_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load user context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    user_doc = context.user_doc
    schema = context.schema
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
    try:
        context = get_web_api_client().get_admin_user_context(
            user_id=user_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("User not found.", "red")
            return redirect(url_for("admin_bp.manage_users"))
        flash(f"Failed to load user context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    user_doc = context.user_doc
    schema = context.schema

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
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle user: {exc}", "red")
    return redirect(url_for("admin_bp.manage_users"))
