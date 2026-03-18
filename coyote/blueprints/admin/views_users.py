"""Admin user-management routes."""

from __future__ import annotations

from copy import deepcopy

from flask import Response, abort, g, jsonify, redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import (
    flash_api_failure,
    flash_api_success,
    raise_page_load_error,
)


def _apply_selected_user_version(
    user_doc: dict, selected_version: int | None, user_id: str | None = None
):
    """Project a versioned user document into the selected historical view.

    Args:
        user_doc: User document returned by the API context endpoint.
        selected_version: Historical version requested by the operator.
        user_id: Optional user identifier used to restore ``_id`` after delta
            application.

    Returns:
        A tuple of ``(user_document, delta)`` where ``delta`` is the applied
        version delta or ``None`` when no historical projection was needed.
    """
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
                user_doc["username"] = user_id
    return user_doc, delta


def _user_schema_from_context(context) -> dict:
    """Extract the user schema from a user-management context payload.

    Args:
        context: API payload object or mapping containing user-management
            context fields.

    Returns:
        The resolved user schema document.

    Raises:
        ApiRequestError: If the schema payload is missing from the context.
    """
    schema = context.get("schema")
    if not schema:
        raise ApiRequestError("User schema payload missing in API response")
    return schema


@admin_bp.route("/users", methods=["GET"])
@login_required
def manage_users() -> str | Response:
    """Render the user-management list page.

    Returns:
        The rendered management page response.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("users"),
            headers=forward_headers(),
        )
        users = payload.get("users", [])
        roles = payload.get("roles", {})
    except AttributeError as exc:
        raise_page_load_error(
            ApiRequestError(f"Invalid user payload: {exc}", status_code=502),
            logger=app.logger,
            log_message="Failed to parse users payload",
            summary="Unable to load the user list.",
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to fetch users via API",
            summary="Unable to load the user list.",
        )
    return render_template("users/manage_users.html", users=users, roles=roles)


@admin_bp.route("/users/validate_username", methods=["POST"])
@login_required
def validate_username() -> Response:
    """Validate whether a username already exists before create or edit.

    Returns:
        A JSON response containing an ``exists`` flag and optional error
        details.
    """
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
    """Validate whether an email address already exists before create or edit.

    Returns:
        A JSON response containing an ``exists`` flag and optional error
        details.
    """
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
    """Render and process the user-creation form.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    try:
        selected_schema_id = request.args.get("schema_id")
        context = get_web_api_client().get_json(
            api_endpoints.admin("users", "create_context"),
            headers=forward_headers(),
            params={"schema_id": selected_schema_id} if selected_schema_id else None,
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to load user schema context via API",
            summary="Unable to load the user creation form.",
        )

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
                    "schema_id": context.selected_schema.get("schema_id"),
                    "form_data": form_data,
                },
            )
            g.audit_metadata = {"user": payload.resource_id}
            flash_api_success("User created successfully.")
        except ApiRequestError as exc:
            flash_api_failure("Unable to create the user.", exc)
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
    """Render and process the user-edit form.

    Args:
        user_id: User identifier for the document being edited.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("users", user_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load user context via API for {user_id}",
            summary="Unable to load the user editing form.",
            not_found_summary="The requested user was not found.",
        )

    user_doc = context.user_doc
    try:
        schema = _user_schema_from_context(context)
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load user schema for {user_id}",
            summary="Unable to load the user schema.",
        )

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
            flash_api_success("User updated successfully.")
        except ApiRequestError as exc:
            flash_api_failure("Unable to update the user.", exc)
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
    """Render the user detail view.

    Args:
        user_id: User identifier for the document being displayed.

    Returns:
        The rendered detail page response.
    """
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("users", user_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load user detail via API for {user_id}",
            summary="Unable to load the user details.",
            not_found_summary="The requested user was not found.",
        )

    try:
        schema = _user_schema_from_context(context)
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load user schema for {user_id}",
            summary="Unable to load the user schema.",
        )

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
    """Delete a user and return to the management page.

    Args:
        user_id: User identifier for the document being deleted.

    Returns:
        A redirect response back to the management page.
    """
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("users", user_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"user": user_id}
        flash_api_success(f"User '{user_id}' deleted successfully.")
    except ApiRequestError as exc:
        flash_api_failure(f"Unable to delete user '{user_id}'.", exc)
    return redirect(url_for("admin_bp.manage_users"))


@admin_bp.route("/users/<user_id>/toggle", methods=["POST", "GET"])
@login_required
def toggle_user_active(user_id: str):
    """Toggle a user's active state and return to the management page.

    Args:
        user_id: User identifier for the document being updated.

    Returns:
        A redirect response back to the management page.
    """
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
        flash_api_success(f"User '{user_id}' is now {'active' if new_status else 'inactive'}.")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash_api_failure(f"Unable to change the status for user '{user_id}'.", exc)
    return redirect(url_for("admin_bp.manage_users"))
