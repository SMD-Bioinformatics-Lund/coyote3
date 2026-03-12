"""Admin permission-management routes."""

from __future__ import annotations

from copy import deepcopy

from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)


def _apply_selected_permission_version(
    permission: dict, selected_version: int | None, perm_id: str | None = None
):
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
                permission["_id"] = perm_id
    return permission, delta


@admin_bp.route("/permissions")
@login_required
def list_permissions() -> str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("permissions"),
            headers=forward_headers(),
        )
        grouped_permissions = payload.get("grouped_permissions", {})
    except AttributeError as exc:
        flash(f"Failed to parse permissions payload: {exc}", "red")
        grouped_permissions = {}
    except ApiRequestError as exc:
        flash(f"Failed to fetch permissions: {exc}", "red")
        grouped_permissions = {}
    return render_template("permissions/permissions.html", grouped_permissions=grouped_permissions)


@admin_bp.route("/permissions/new", methods=["GET", "POST"])
@login_required
def create_permission() -> Response | str:
    try:
        selected_schema_id = request.args.get("schema_id")
        context = get_web_api_client().get_json(
            api_endpoints.admin("permissions", "create_context"),
            headers=forward_headers(),
            params={"schema_id": selected_schema_id} if selected_schema_id else None,
        )
    except ApiRequestError as exc:
        flash(f"Failed to load permission schema context: {exc}", "red")
        return redirect(url_for("admin_bp.list_permissions"))

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
                    "schema_id": context.selected_schema.get("_id"),
                    "form_data": form_data,
                },
            )
            g.audit_metadata = {"permission": payload.resource_id}
            flash(f"Permission policy '{payload.resource_id}' created.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to create permission policy: {exc}", "red")
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
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("permissions", perm_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load permission context: {exc}", "red")
        return redirect(url_for("admin_bp.list_permissions"))

    selected_version = request.args.get("version", type=int)
    permission, delta = _apply_selected_permission_version(context.permission, selected_version, perm_id)

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
            flash(f"Permission policy '{perm_id}' updated.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update permission policy: {exc}", "red")
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
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("permissions", perm_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load permission context: {exc}", "red")
        return redirect(url_for("admin_bp.list_permissions"))

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
        flash(f"Permission '{perm_id}' is now {'Active' if new_status else 'Inactive'}.", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle permission policy: {exc}", "red")
    return redirect(url_for("admin_bp.list_permissions"))


@admin_bp.route("/permissions/<perm_id>/delete", methods=["GET"])
@login_required
def delete_permission(perm_id: str) -> Response:
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("permissions", perm_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"permission": perm_id}
        flash(f"Permission policy '{perm_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to delete permission policy: {exc}", "red")
    return redirect(url_for("admin_bp.list_permissions"))
