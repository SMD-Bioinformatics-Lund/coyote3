"""Admin role-management routes."""

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


def _apply_selected_role_version(role: dict, selected_version: int | None, role_id: str | None = None):
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
                role["_id"] = role_id
    return role, delta


@admin_bp.route("/roles")
@login_required
def list_roles() -> str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("roles"),
            headers=forward_headers(),
        )
        roles = payload.get("roles", [])
    except AttributeError as exc:
        flash(f"Failed to parse roles payload: {exc}", "red")
        roles = []
    except ApiRequestError as exc:
        flash(f"Failed to fetch roles: {exc}", "red")
        roles = []
    return render_template("roles/roles.html", roles=roles)


@admin_bp.route("/roles/new", methods=["GET", "POST"])
@login_required
def create_role() -> Response | str:
    try:
        selected_schema_id = request.args.get("schema_id")
        context = get_web_api_client().get_json(
            api_endpoints.admin("roles", "create_context"),
            headers=forward_headers(),
            params={"schema_id": selected_schema_id} if selected_schema_id else None,
        )
    except ApiRequestError as exc:
        flash(f"Failed to load role schema context: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

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
                    "schema_id": context.selected_schema.get("_id"),
                    "form_data": form_data,
                },
            )
            g.audit_metadata = {"role": payload.resource_id}
            flash(f"Role '{payload.resource_id}' created successfully.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to create role: {exc}", "red")
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
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("roles", role_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load role context: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

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
            flash(f"Role '{role_id}' updated successfully.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update role: {exc}", "red")
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
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("roles", role_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load role context: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

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
        flash(f"Role '{role_id}' is now {'Active' if new_status else 'Inactive'}.", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle role: {exc}", "red")
    return redirect(url_for("admin_bp.list_roles"))


@admin_bp.route("/roles/<role_id>/delete", methods=["GET"])
@login_required
def delete_role(role_id: str) -> Response:
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("roles", role_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"role": role_id}
        flash(f"Role '{role_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to delete role: {exc}", "red")
    return redirect(url_for("admin_bp.list_roles"))
