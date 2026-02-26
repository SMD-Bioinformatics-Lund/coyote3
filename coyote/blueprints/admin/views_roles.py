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

"""Admin role-management routes."""

from copy import deepcopy

from flask import Response, abort, flash, g, redirect, render_template, request, url_for

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.audit_logs.decorators import log_action
from coyote.services.auth.decorators import require
from coyote.web_api.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@admin_bp.route("/roles")
@require("view_role", min_role="admin", min_level=99999)
def list_roles() -> str:
    try:
        payload = get_web_api_client().get_admin_roles(headers=build_forward_headers(request.headers))
        roles = payload.roles
    except ApiRequestError as exc:
        flash(f"Failed to fetch roles: {exc}", "red")
        roles = []
    return render_template("roles/roles.html", roles=roles)


@admin_bp.route("/roles/new", methods=["GET", "POST"])
@require("create_role", min_role="admin", min_level=99999)
@log_action(action_name="create_role", call_type="admin_call")
def create_role() -> Response | str:
    try:
        context = get_web_api_client().get_admin_role_create_context(
            schema_id=request.args.get("schema_id"),
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        flash(f"Failed to load role schema context: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

    schema = context.schema
    active_schemas = context.schemas

    if request.method == "POST":
        form_data: dict[str, str | list[str]] = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            payload = get_web_api_client().create_admin_role(
                schema_id=context.selected_schema.get("_id"),
                form_data=form_data,
                headers=build_forward_headers(request.headers),
            )
            g.audit_metadata = {"role": payload.resource_id}
            flash(f"Role '{payload.resource_id}' created successfully.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to create role: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

    return render_template(
        "roles/create_role.html",
        schema=schema,
        selected_schema=schema,
        schemas=active_schemas,
    )


@admin_bp.route("/roles/<role_id>/edit", methods=["GET", "POST"])
@require("edit_role", min_role="admin", min_level=99999)
@log_action(action_name="edit_role", call_type="admin_call")
def edit_role(role_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_admin_role_context(
            role_id=role_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load role context: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

    role = context.role
    schema = context.schema

    selected_version = request.args.get("version", type=int)
    delta = None

    if selected_version and selected_version != role.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(role.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = role["version_history"][version_index].get("delta", {})
            role = util.admin.apply_version_delta(deepcopy(role), delta_blob)
            delta = delta_blob
            role["_id"] = role_id

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        try:
            get_web_api_client().update_admin_role(
                role_id=role_id,
                form_data=form_data,
                headers=build_forward_headers(request.headers),
            )
            g.audit_metadata = {"role": role_id}
            flash(f"Role '{role_id}' updated successfully.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update role: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

    return render_template(
        "roles/edit_role.html",
        schema=schema,
        role_doc=role,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/roles/<role_id>/view", methods=["GET"])
@require("view_role", min_role="admin", min_level=99999)
@log_action(action_name="view_role", call_type="admin_call")
def view_role(role_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_admin_role_context(
            role_id=role_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to load role context: {exc}", "red")
        return redirect(url_for("admin_bp.list_roles"))

    role = context.role
    schema = context.schema

    selected_version = request.args.get("version", type=int)
    delta = None
    if selected_version and selected_version != role.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(role.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = role["version_history"][version_index].get("delta", {})
            delta = delta_blob
            role = util.admin.apply_version_delta(deepcopy(role), delta_blob)

    return render_template(
        "roles/view_role.html",
        schema=schema,
        role_doc=role,
        selected_version=selected_version or role.get("version"),
        delta=delta,
    )


@admin_bp.route("/roles/<role_id>/toggle", methods=["POST", "GET"])
@require("edit_role", min_role="admin", min_level=99999)
@log_action(action_name="edit_role", call_type="admin_call")
def toggle_role_active(role_id: str) -> Response:
    try:
        payload = get_web_api_client().toggle_admin_role(
            role_id=role_id,
            headers=build_forward_headers(request.headers),
        )
        new_status = bool(payload.meta.get("is_active", False))
        g.audit_metadata = {
            "role": role_id,
            "role_status": "Active" if new_status else "Inactive",
        }
        flash(
            f"Role '{role_id}' is now {'Active' if new_status else 'Inactive'}.",
            "green",
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle role: {exc}", "red")
    return redirect(url_for("admin_bp.list_roles"))


@admin_bp.route("/roles/<role_id>/delete", methods=["GET"])
@require("delete_role", min_role="admin", min_level=99999)
@log_action(action_name="delete_role", call_type="admin_call")
def delete_role(role_id: str) -> Response:
    try:
        get_web_api_client().delete_admin_role(
            role_id=role_id,
            headers=build_forward_headers(request.headers),
        )
        g.audit_metadata = {"role": role_id}
        flash(f"Role '{role_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to delete role: {exc}", "red")
    return redirect(url_for("admin_bp.list_roles"))
