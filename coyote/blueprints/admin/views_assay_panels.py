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

"""Admin assay panel routes (`/asp/*`)."""

from copy import deepcopy

from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.audit_logs.decorators import log_action
from coyote.services.auth.decorators import require
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@admin_bp.route("/asp/manage", methods=["GET"])
@require("view_asp", min_role="user", min_level=9)
def manage_assay_panels():
    try:
        payload = get_web_api_client().get_admin_asp(headers=build_forward_headers(request.headers))
        panels = payload.panels
    except ApiRequestError as exc:
        flash(f"Failed to fetch panels: {exc}", "red")
        panels = []
    return render_template("asp/manage_asp.html", panels=panels)


@admin_bp.route("/asp/new", methods=["GET", "POST"])
@require("create_asp", min_role="manager", min_level=99)
@log_action(action_name="create_asp", call_type="manager_call")
def create_assay_panel():
    try:
        context = get_web_api_client().get_admin_asp_create_context(
            schema_id=request.args.get("schema_id"),
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        flash(f"Failed to load panel create context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    active_schemas = context.schemas
    schema = context.schema

    if request.method == "POST":
        form_data: dict[str, list[str] | str] = {
            key: (
                request.form.getlist(key)
                if len(vals := request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }

        covered_genes = util.admin.extract_gene_list(
            request.files.get("genes_file"), form_data.get("genes_paste", "")
        )
        germline_genes = util.admin.extract_gene_list(
            request.files.get("germline_genes_file"),
            form_data.get("germline_genes_paste", ""),
        )

        config = util.admin.process_form_to_config(form_data, schema)
        config["_id"] = config["assay_name"]
        config["covered_genes"] = covered_genes
        config["covered_genes_count"] = len(covered_genes)
        config["germline_genes"] = germline_genes
        config["germline_genes_count"] = len(germline_genes)
        config.update(
            {
                "schema_name": schema["_id"],
                "schema_version": schema["version"],
                "version": 1,
            }
        )

        config = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=deepcopy(config),
            is_new=True,
        )

        try:
            get_web_api_client().create_admin_asp(
                config=config,
                headers=build_forward_headers(request.headers),
            )
            g.audit_metadata = {"panel": config["_id"]}
            flash(f"Panel {config['assay_name']} created successfully!", "green")
        except ApiRequestError as exc:
            flash(f"Failed to create panel: {exc}", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    return render_template(
        "asp/create_asp.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=context.selected_schema,
    )


@admin_bp.route("/asp/<assay_panel_id>/edit", methods=["GET", "POST"])
@require("edit_asp", min_role="manager", min_level=99)
@log_action(action_name="edit_asp", call_type="manager_call")
def edit_assay_panel(assay_panel_id: str) -> str | Response:
    try:
        context = get_web_api_client().get_admin_asp_context(
            assay_panel_id=assay_panel_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("Panel or schema not found.", "red")
        else:
            flash(f"Failed to load panel context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    panel = context.panel
    schema = context.schema

    selected_version = request.args.get("version", type=int)
    delta = None

    if selected_version and selected_version != panel.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(panel.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = panel["version_history"][version_index].get("delta", {})
            panel = util.admin.apply_version_delta(panel, delta_blob)
            delta = delta_blob
            panel["_id"] = assay_panel_id

    if request.method == "POST":
        form_data: dict[str, list[str] | str] = {
            key: (
                request.form.getlist(key)
                if len(vals := request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }

        covered_genes = util.admin.extract_gene_list(
            request.files.get("genes_file"),
            form_data.get("genes_paste", ""),
        )

        if not "genes_file" in request.files and not "genes_paste" in form_data:
            covered_genes = panel.get("covered_genes", [])

        germline_genes = util.admin.extract_gene_list(
            request.files.get("germline_genes_file"),
            form_data.get("germline_genes_paste", ""),
        )
        if not "germline_genes_file" in request.files and not "germline_genes_paste" in form_data:
            germline_genes = panel.get("germline_genes", [])

        updated = util.admin.process_form_to_config(form_data, schema)
        updated["_id"] = panel["_id"]
        updated["covered_genes"] = covered_genes
        updated["covered_genes_count"] = len(covered_genes)
        updated["germline_genes"] = germline_genes
        updated["germline_genes_count"] = len(germline_genes)
        updated["updated_by"] = current_user.email
        updated["updated_on"] = util.common.utc_now()
        updated["schema_name"] = schema["_id"]
        updated["schema_version"] = schema["version"]
        updated["version"] = panel.get("version", 1) + 1

        updated = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=updated,
            old_config=panel,
            is_new=False,
        )

        try:
            get_web_api_client().update_admin_asp(
                assay_panel_id=assay_panel_id,
                config=updated,
                headers=build_forward_headers(request.headers),
            )
            g.audit_metadata = {"panel": assay_panel_id}
            flash(f"Panel '{panel['assay_name']}' updated successfully!", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update panel: {exc}", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    return render_template(
        "asp/edit_asp.html",
        schema=schema,
        panel=panel,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/asp/<assay_panel_id>/view", methods=["GET"])
@require("view_asp", min_role="user", min_level=9)
def view_assay_panel(assay_panel_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_admin_asp_context(
            assay_panel_id=assay_panel_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash(f"Panel '{assay_panel_id}' not found!", "red")
        else:
            flash(f"Failed to load panel context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    panel = context.panel
    schema = context.schema
    selected_version = request.args.get("version", type=int)
    delta = None

    if selected_version and selected_version != panel.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(panel.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = panel["version_history"][version_index].get("delta", {})
            panel = util.admin.apply_version_delta(panel, delta_blob)
            delta = delta_blob
            panel["_id"] = assay_panel_id

    return render_template(
        "asp/view_asp.html",
        panel=panel,
        schema=schema,
        selected_version=selected_version or panel.get("version"),
        delta=delta,
    )


@admin_bp.route("/asp/<panel_id>/print", methods=["GET"])
@require("view_asp", min_role="user", min_level=9)
@log_action(action_name="print_asp", call_type="viewer_call")
def print_assay_panel(panel_id: str) -> str | Response:
    try:
        context = get_web_api_client().get_admin_asp_context(
            assay_panel_id=panel_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("Panel not found.", "red")
        else:
            flash(f"Failed to load panel context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    panel = context.panel
    schema = context.schema

    selected_version = request.args.get("version", type=int)
    if selected_version and selected_version != panel.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(panel.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = panel["version_history"][version_index].get("delta", {})
            panel = util.admin.apply_version_delta(deepcopy(panel), delta_blob)
            panel["_id"] = panel_id
            panel["version"] = selected_version

    return render_template(
        "asp/print_asp.html",
        schema=schema,
        config=panel,
        now=util.common.utc_now(),
        selected_version=selected_version,
    )


@admin_bp.route("/asp/<assay_panel_id>/toggle", methods=["POST", "GET"])
@require("edit_asp", min_role="manager", min_level=99)
@log_action(action_name="toggle_asp", call_type="manager_call")
def toggle_assay_panel_active(assay_panel_id: str) -> Response:
    try:
        payload = get_web_api_client().toggle_admin_asp(
            assay_panel_id=assay_panel_id,
            headers=build_forward_headers(request.headers),
        )
        new_status = bool(payload.meta.get("is_active", False))
        g.audit_metadata = {
            "panel": assay_panel_id,
            "panel_status": "Active" if new_status else "Inactive",
        }
        flash(f"Panel '{assay_panel_id}' status toggled!", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle panel: {exc}", "red")
    return redirect(url_for("admin_bp.manage_assay_panels"))


@admin_bp.route("/asp/<assay_panel_id>/delete", methods=["GET"])
@require("delete_asp", min_role="admin", min_level=99999)
@log_action(action_name="delete_asp", call_type="admin_call")
def delete_assay_panel(assay_panel_id: str) -> Response:
    try:
        get_web_api_client().delete_admin_asp(
            assay_panel_id=assay_panel_id,
            headers=build_forward_headers(request.headers),
        )
        g.audit_metadata = {"panel": assay_panel_id}
        flash(f"Panel '{assay_panel_id}' deleted!", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete panel: {exc}", "red")
    return redirect(url_for("admin_bp.manage_assay_panels"))
