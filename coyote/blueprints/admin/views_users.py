"""Admin user-management routes."""

from __future__ import annotations

from copy import deepcopy

from flask import Response, abort, flash, g, jsonify, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)


def _apply_selected_user_version(user_doc: dict, selected_version: int | None, user_id: str | None = None):
    delta = None
    if selected_version and selected_version != user_doc.get("version"):
        version_index = next(
            (
                i
                for i, version_entry in enumerate(user_doc.get("version_history", []))
                if version_entry["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = user_doc["version_history"][version_index].get("delta", {})
            user_doc = util.admin.apply_version_delta(deepcopy(user_doc), delta_blob)
            delta = delta_blob
            if user_id:
                user_doc["_id"] = user_id
    return user_doc, delta


def _user_schema_from_context(context) -> dict:
    schema = context.get("schema")
    if not schema:
        raise ApiRequestError("User schema payload missing in API response")
    return schema


@admin_bp.route("/users", methods=["GET"])
@login_required
def manage_users() -> str | Response:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("users"),
            headers=forward_headers(),
        )
        users = payload.get("users", [])
        roles = payload.get("roles", {})
    except AttributeError as exc:
        flash(f"Failed to parse users payload: {exc}", "red")
        users = []
        roles = {}
    except ApiRequestError as exc:
        flash(f"Failed to fetch users: {exc}", "red")
        users = []
        roles = {}
    return render_template("users/manage_users.html", users=users, roles=roles)


@admin_bp.route("/users/validate_username", methods=["POST"])
@login_required
def validate_username() -> Response:
    username = request.json.get("username").lower()
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("users", "validate_username"),
            headers=forward_headers(),
            json_body={"username": username},
        )
        return jsonify({"exists": bool(payload.get("exists", False))})
    except ApiRequestError as exc:
        return jsonify({"exists": False, "error": str(exc)}), 502


@admin_bp.route("/users/validate_email", methods=["POST"])
@login_required
def validate_email():
    email = request.json.get("email").lower()
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("users", "validate_email"),
            headers=forward_headers(),
            json_body={"email": email},
        )
        return jsonify({"exists": bool(payload.get("exists", False))})
    except ApiRequestError as exc:
        return jsonify({"exists": False, "error": str(exc)}), 502


@admin_bp.route("/users/new", methods=["GET", "POST"])
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

    if request.method == "POST":
        form_data: dict[str, str | list[str]] = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            payload = get_web_api_client().post_json(
                api_endpoints.admin("users"),
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
        schema=context.schema,
        schemas=context.schemas,
        selected_schema=context.selected_schema,
        assay_group_map=context.assay_group_map,
        role_map=context.role_map,
    )


@admin_bp.route("/users/<user_id>/edit", methods=["GET", "POST"])
@login_required
def edit_user(user_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("users", user_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load user context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    user_doc = context.user_doc
    try:
        schema = _user_schema_from_context(context)
    except ApiRequestError as exc:
        flash(f"Failed to load user schema: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    selected_version = request.args.get("version", type=int)
    user_doc, delta = _apply_selected_user_version(user_doc, selected_version, user_id)

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            get_web_api_client().put_json(
                api_endpoints.admin("users", user_id),
                headers=forward_headers(),
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
        assay_group_map=context.assay_group_map,
        role_map=context.role_map,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/users/<user_id>/view", methods=["GET"])
@login_required
def view_user(user_id: str) -> str | Response:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("users", user_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("User not found.", "red")
            return redirect(url_for("admin_bp.manage_users"))
        flash(f"Failed to load user context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    try:
        schema = _user_schema_from_context(context)
    except ApiRequestError as exc:
        flash(f"Failed to load user schema: {exc}", "red")
        return redirect(url_for("admin_bp.manage_users"))

    selected_version = request.args.get("version", type=int)
    user_doc, delta = _apply_selected_user_version(context.user_doc, selected_version)

    return render_template(
        "users/user_view.html",
        schema=schema,
        user=user_doc,
        selected_version=selected_version or user_doc.get("version"),
        delta=delta,
    )


@admin_bp.route("/users/<user_id>/delete", methods=["GET"])
@login_required
def delete_user(user_id: str) -> Response:
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("users", user_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"user": user_id}
        flash(f"User '{user_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete user: {exc}", "red")
    return redirect(url_for("admin_bp.manage_users"))


@admin_bp.route("/users/<user_id>/toggle", methods=["POST", "GET"])
@login_required
def toggle_user_active(user_id: str):
    try:
        payload = get_web_api_client().patch_json(
            api_endpoints.admin("users", user_id, "status"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", True))
        g.audit_metadata = {
            "user": user_id,
            "user_status": "Active" if new_status else "Inactive",
        }
        flash(f"User: '{user_id}' is now {'active' if new_status else 'inactive'}.", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle user: {exc}", "red")
    return redirect(url_for("admin_bp.manage_users"))
