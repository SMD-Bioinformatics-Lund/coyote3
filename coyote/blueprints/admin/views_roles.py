"""Admin role-management routes."""

from __future__ import annotations

from copy import deepcopy

from flask import Response, abort, g, redirect, render_template, request, url_for
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


def _apply_selected_role_version(
    role: dict, selected_version: int | None, role_id: str | None = None
):
    """Return the selected historical role version for diff-aware rendering.

    Args:
        role: Role document returned by the API context endpoint.
        selected_version: Historical version requested by the operator.
        role_id: Optional role identifier used to restore ``_id`` after delta
            application.

    Returns:
        A tuple of ``(role_document, delta)`` where ``delta`` is the applied
        version delta or ``None`` when no historical projection was needed.
    """
    delta = None
    if selected_version and selected_version != role.get("version"):
        version_index = next(
            (
                i
                for i, version_entry in enumerate(role.get("version_history", []))
                if version_entry["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = role["version_history"][version_index].get("delta", {})
            role = util.admin.apply_version_delta(deepcopy(role), delta_blob)
            delta = delta_blob
            if role_id:
                role["role_id"] = role_id
    return role, delta


@admin_bp.route("/roles")
@login_required
def list_roles() -> str:
    """Render the role-management page.

    Returns:
        The rendered role-management page response.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("roles"),
            headers=forward_headers(),
        )
        roles = payload.get("roles", [])
    except AttributeError as exc:
        app.logger.error("Failed to parse roles payload: %s", exc)
        raise_page_load_error(
            ApiRequestError(str(exc)),
            logger=app.logger,
            log_message="Failed to parse role list payload",
            summary="Unable to load roles.",
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to fetch roles",
            summary="Unable to load roles.",
        )
    return render_template("roles/roles.html", roles=roles)


@admin_bp.route("/roles/new", methods=["GET", "POST"])
@login_required
def create_role() -> Response | str:
    """Create a role from the configured role schema.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    try:
        selected_schema_id = request.args.get("schema_id")
        context = get_web_api_client().get_json(
            api_endpoints.admin("roles", "create_context"),
            headers=forward_headers(),
            params={"schema_id": selected_schema_id} if selected_schema_id else None,
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to load role create context",
            summary="Unable to load the role creation form.",
        )

    if request.method == "POST":
        form_data: dict[str, str | list[str]] = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            payload = get_web_api_client().post_json(
                api_endpoints.admin("roles"),
                headers=forward_headers(),
                json_body={
                    "schema_id": context.selected_schema.get("schema_id"),
                    "form_data": form_data,
                },
            )
            g.audit_metadata = {"role": payload.resource_id}
            flash_api_success(f"Role '{payload.resource_id}' created successfully.")
        except ApiRequestError as exc:
            flash_api_failure("Failed to create role.", exc)
        return redirect(url_for("admin_bp.list_roles"))

    return render_template(
        "roles/create_role.html",
        schema=context.schema,
        selected_schema=context.selected_schema,
        schemas=context.schemas,
    )


@admin_bp.route("/roles/<role_id>/edit", methods=["GET", "POST"])
@login_required
def edit_role(role_id: str) -> Response | str:
    """Edit an existing role definition.

    Args:
        role_id: Role identifier for the document being edited.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("roles", role_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load role context for {role_id}",
            summary="Unable to load the role.",
            not_found_summary="Role not found.",
        )

    role, delta = _apply_selected_role_version(
        context.role,
        request.args.get("version", type=int),
        role_id,
    )

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            get_web_api_client().put_json(
                api_endpoints.admin("roles", role_id),
                headers=forward_headers(),
                json_body={"form_data": form_data},
            )
            g.audit_metadata = {"role": role_id}
            flash_api_success(f"Role '{role_id}' updated successfully.")
        except ApiRequestError as exc:
            flash_api_failure("Failed to update role.", exc)
        return redirect(url_for("admin_bp.list_roles"))

    return render_template(
        "roles/edit_role.html",
        schema=context.schema,
        role_doc=role,
        selected_version=request.args.get("version", type=int),
        delta=delta,
    )


@admin_bp.route("/roles/<role_id>/view", methods=["GET"])
@login_required
def view_role(role_id: str) -> Response | str:
    """Display a read-only role view.

    Args:
        role_id: Role identifier for the document being displayed.

    Returns:
        The rendered detail page response.
    """
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("roles", role_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load role view context for {role_id}",
            summary="Unable to load the role.",
            not_found_summary="Role not found.",
        )

    selected_version = request.args.get("version", type=int)
    role, delta = _apply_selected_role_version(context.role, selected_version)

    return render_template(
        "roles/view_role.html",
        schema=context.schema,
        role_doc=role,
        selected_version=selected_version or role.get("version"),
        delta=delta,
    )


@admin_bp.route("/roles/<role_id>/toggle", methods=["POST", "GET"])
@login_required
def toggle_role_active(role_id: str) -> Response:
    """Toggle the active flag on a role.

    Args:
        role_id: Role identifier for the document being updated.

    Returns:
        A redirect response back to the management page.
    """
    try:
        payload = get_web_api_client().patch_json(
            api_endpoints.admin("roles", role_id, "status"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", True))
        g.audit_metadata = {
            "role": role_id,
            "role_status": "Active" if new_status else "Inactive",
        }
        flash_api_success(f"Role '{role_id}' is now {'Active' if new_status else 'Inactive'}.")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash_api_failure("Failed to update role status.", exc)
    return redirect(url_for("admin_bp.list_roles"))


@admin_bp.route("/roles/<role_id>/delete", methods=["GET"])
@login_required
def delete_role(role_id: str) -> Response:
    """Delete a role definition.

    Args:
        role_id: Role identifier for the document being deleted.

    Returns:
        A redirect response back to the management page.
    """
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("roles", role_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"role": role_id}
        flash_api_success(f"Role '{role_id}' deleted successfully.")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash_api_failure("Failed to delete role.", exc)
    return redirect(url_for("admin_bp.list_roles"))
