"""Admin permission-management routes."""

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


def _apply_selected_permission_version(
    permission: dict, selected_version: int | None, perm_id: str | None = None
):
    """Return the selected historical permission version for diff-aware rendering.

    Args:
        permission: Permission document returned by the API context endpoint.
        selected_version: Historical version requested by the operator.
        perm_id: Optional permission identifier used to restore ``_id`` after
            delta application.

    Returns:
        A tuple of ``(permission_document, delta)`` where ``delta`` is the
        applied version delta or ``None`` when no historical projection was
        needed.
    """
    delta = None
    if selected_version and selected_version != permission.get("version"):
        version_index = next(
            (
                i
                for i, version_entry in enumerate(permission.get("version_history", []))
                if version_entry["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = permission["version_history"][version_index].get("delta", {})
            permission = util.admin.apply_version_delta(deepcopy(permission), delta_blob)
            delta = delta_blob
            if perm_id:
                permission["permission_id"] = perm_id
    return permission, delta


@admin_bp.route("/permissions")
@login_required
def list_permissions() -> str:
    """Render the permission-management page.

    Returns:
        The rendered permission-management page response.
    """
    q = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    per_page = max(1, min(request.args.get("per_page", default=30, type=int) or 30, 200))
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("permissions"),
            headers=forward_headers(),
            params={"q": q, "page": page, "per_page": per_page},
        )
        grouped_permissions = payload.get("grouped_permissions", {})
        pagination = payload.get("pagination", {})
    except AttributeError as exc:
        app.logger.error("Failed to parse permissions payload: %s", exc)
        raise_page_load_error(
            ApiRequestError(str(exc)),
            logger=app.logger,
            log_message="Failed to parse permission list payload",
            summary="Unable to load permissions.",
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to fetch permissions",
            summary="Unable to load permissions.",
        )
    return render_template(
        "permissions/permissions.html",
        grouped_permissions=grouped_permissions,
        q=q,
        page=pagination.get("page", page),
        per_page=pagination.get("per_page", per_page),
        total=pagination.get("total", 0),
        has_next=pagination.get("has_next", False),
    )


@admin_bp.route("/permissions/new", methods=["GET", "POST"])
@login_required
def create_permission() -> Response | str:
    """Create a permission policy from the configured schema.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    try:
        selected_schema_id = request.args.get("schema_id")
        context = get_web_api_client().get_json(
            api_endpoints.admin("permissions", "create_context"),
            headers=forward_headers(),
            params={"schema_id": selected_schema_id} if selected_schema_id else None,
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to load permission create context",
            summary="Unable to load the permission creation form.",
        )

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            payload = get_web_api_client().post_json(
                api_endpoints.admin("permissions"),
                headers=forward_headers(),
                json_body={
                    "schema_id": context.selected_schema.get("schema_id"),
                    "form_data": form_data,
                },
            )
            g.audit_metadata = {"permission": payload.resource_id}
            flash_api_success(f"Permission policy '{payload.resource_id}' created.")
        except ApiRequestError as exc:
            flash_api_failure("Failed to create permission policy.", exc)
        return redirect(url_for("admin_bp.list_permissions"))

    return render_template(
        "permissions/create_permission.html",
        schema=context.schema,
        schemas=context.schemas,
        selected_schema=context.selected_schema,
    )


@admin_bp.route("/permissions/<perm_id>/edit", methods=["GET", "POST"])
@login_required
def edit_permission(perm_id: str) -> Response | str:
    """Edit a permission policy.

    Args:
        perm_id: Permission identifier for the document being edited.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("permissions", perm_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load permission context for {perm_id}",
            summary="Unable to load the permission policy.",
            not_found_summary="Permission policy not found.",
        )

    selected_version = request.args.get("version", type=int)
    permission, delta = _apply_selected_permission_version(
        context.permission, selected_version, perm_id
    )

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            get_web_api_client().put_json(
                api_endpoints.admin("permissions", perm_id),
                headers=forward_headers(),
                json_body={"form_data": form_data},
            )
            g.audit_metadata = {"permission": perm_id}
            flash_api_success(f"Permission policy '{perm_id}' updated.")
        except ApiRequestError as exc:
            flash_api_failure("Failed to update permission policy.", exc)
        return redirect(url_for("admin_bp.list_permissions"))

    return render_template(
        "permissions/edit_permission.html",
        schema=context.schema,
        permission=permission,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/permissions/<perm_id>/view", methods=["GET"])
@login_required
def view_permission(perm_id: str) -> str | Response:
    """Display a read-only permission policy view.

    Args:
        perm_id: Permission identifier for the document being displayed.

    Returns:
        The rendered detail page response.
    """
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("permissions", perm_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load permission view context for {perm_id}",
            summary="Unable to load the permission policy.",
            not_found_summary="Permission policy not found.",
        )

    selected_version = request.args.get("version", type=int)
    permission, delta = _apply_selected_permission_version(context.permission, selected_version)

    return render_template(
        "permissions/view_permission.html",
        schema=context.schema,
        permission=permission,
        selected_version=selected_version or permission.get("version"),
        delta=delta,
    )


@admin_bp.route("/permissions/<perm_id>/toggle", methods=["POST", "GET"])
@login_required
def toggle_permission_active(perm_id: str) -> Response:
    """Toggle the active flag on a permission policy.

    Args:
        perm_id: Permission identifier for the document being updated.

    Returns:
        A redirect response back to the management page.
    """
    try:
        payload = get_web_api_client().patch_json(
            api_endpoints.admin("permissions", perm_id, "status"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", True))
        g.audit_metadata = {
            "permission": perm_id,
            "permission_status": "Active" if new_status else "Inactive",
        }
        flash_api_success(
            f"Permission '{perm_id}' is now {'Active' if new_status else 'Inactive'}."
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash_api_failure("Failed to update permission policy status.", exc)
    return redirect(url_for("admin_bp.list_permissions"))


@admin_bp.route("/permissions/<perm_id>/delete", methods=["GET"])
@login_required
def delete_permission(perm_id: str) -> Response:
    """Delete a permission policy.

    Args:
        perm_id: Permission identifier for the document being deleted.

    Returns:
        A redirect response back to the management page.
    """
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("permissions", perm_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"permission": perm_id}
        flash_api_success(f"Permission policy '{perm_id}' deleted successfully.")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash_api_failure("Failed to delete permission policy.", exc)
    return redirect(url_for("admin_bp.list_permissions"))
