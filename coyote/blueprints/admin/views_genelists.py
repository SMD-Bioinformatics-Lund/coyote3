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

"""Admin in-silico genelist routes."""

from copy import deepcopy

from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.audit_logs.decorators import log_action
from coyote.services.auth.decorators import require
from coyote.integrations.api.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@admin_bp.route("/genelists", methods=["GET"])
@require("view_isgl", min_role="user", min_level=9)
def manage_genelists() -> str:
    try:
        payload = get_web_api_client().get_admin_genelists(headers=build_forward_headers(request.headers))
        genelists = payload.genelists
    except ApiRequestError as exc:
        flash(f"Failed to fetch genelists: {exc}", "red")
        genelists = []
    return render_template("isgl/manage_isgl.html", genelists=genelists, is_public=False)


@admin_bp.route("/genelists/new", methods=["GET", "POST"])
@require("create_isgl", min_role="manager", min_level=99)
@log_action(action_name="create_genelist", call_type="manager_call")
def create_genelist() -> Response | str:
    try:
        context = get_web_api_client().get_admin_genelist_create_context(
            schema_id=request.args.get("schema_id"),
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        flash(f"Failed to load genelist create context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    active_schemas = context.schemas
    schema = context.schema_payload
    assay_group_map = context.assay_group_map

    if request.method == "POST":
        form_data: dict[str, list[str] | str] = {
            key: (
                request.form.getlist(key)
                if len(vals := request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }

        genes = []
        if "genes_file" in request.files and request.files["genes_file"].filename:
            file = request.files["genes_file"]
            content = file.read().decode("utf-8")
            genes = [g.strip() for g in content.replace(",", "\n").splitlines() if g.strip()]
        elif "genes_paste" in form_data and form_data["genes_paste"].strip():
            genes = [
                g.strip()
                for g in form_data["genes_paste"].replace(",", "\n").splitlines()
                if g.strip()
            ]

        genes = list(set(deepcopy(genes)))
        genes.sort()
        config = util.admin.process_form_to_config(form_data, schema)
        config["_id"] = config["name"]
        config["genes"] = genes
        config["schema_name"] = schema["_id"]
        config["schema_version"] = schema["version"]
        config["gene_count"] = len(genes)
        config = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=deepcopy(config),
            is_new=True,
        )

        try:
            get_web_api_client().create_admin_genelist(
                config=config,
                headers=build_forward_headers(request.headers),
            )
            flash(f"Genelist {config['name']} created successfully!", "green")
        except ApiRequestError as exc:
            flash(f"Failed to create genelist: {exc}", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    return render_template(
        "isgl/create_isgl.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=context.selected_schema,
        assay_group_map=assay_group_map,
    )


@admin_bp.route("/genelists/<genelist_id>/edit", methods=["GET", "POST"])
@require("edit_isgl", min_role="manager", min_level=99)
@log_action(action_name="edit_genelist", call_type="manager_call")
def edit_genelist(genelist_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_admin_genelist_context(
            genelist_id=genelist_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("Genelist not found!", "red")
            return redirect(url_for("admin_bp.manage_genelists"))
        flash(f"Failed to load genelist context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    genelist = context.genelist
    schema = context.schema_payload
    assay_group_map = context.assay_group_map

    selected_version = request.args.get("version", type=int)
    delta = None
    if selected_version and selected_version != genelist.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(genelist.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = genelist["version_history"][version_index].get("delta", {})
            genelist = util.admin.apply_version_delta(deepcopy(genelist), delta_blob)
            delta = delta_blob
            genelist["_id"] = genelist_id

    if request.method == "POST":
        form_data = {
            key: (
                request.form.getlist(key)
                if len(vals := request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }

        updated = util.admin.process_form_to_config(form_data, schema)

        genes = []
        if "genes_file" in request.files and request.files["genes_file"].filename:
            file = request.files["genes_file"]
            content = file.read().decode("utf-8")
            genes = [g.strip() for g in content.replace(",", "\n").splitlines() if g.strip()]
        elif "genes_paste" in form_data and form_data["genes_paste"].strip():
            pasted = form_data["genes_paste"].replace(",", "\n")
            genes = [g.strip() for g in pasted.splitlines() if g.strip()]
        else:
            genes = genelist.get("genes", [])

        genes = list(set(deepcopy(genes)))
        genes.sort()
        updated["genes"] = genes
        updated["gene_count"] = len(genes)
        updated["updated_by"] = current_user.email
        updated["updated_on"] = util.common.utc_now()
        updated["schema_name"] = schema["_id"]
        updated["schema_version"] = schema["version"]
        updated["version"] = genelist.get("version", 1) + 1

        updated = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=updated,
            old_config=genelist,
            is_new=False,
        )
        try:
            get_web_api_client().update_admin_genelist(
                genelist_id=genelist_id,
                config=updated,
                headers=build_forward_headers(request.headers),
            )
            g.audit_metadata = {"genelist": genelist_id}
            flash(f"Genelist '{genelist_id}' updated successfully!", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update genelist: {exc}", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    return render_template(
        "isgl/edit_isgl.html",
        isgl=genelist,
        schema=schema,
        assay_group_map=assay_group_map,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/genelists/<genelist_id>/toggle", methods=["GET"])
@require("edit_isgl", min_role="manager", min_level=99)
@log_action(action_name="toggle_genelist", call_type="manager_call")
def toggle_genelist(genelist_id: str) -> Response:
    try:
        payload = get_web_api_client().toggle_admin_genelist(
            genelist_id=genelist_id,
            headers=build_forward_headers(request.headers),
        )
        new_status = bool(payload.meta.get("is_active", True))
        g.audit_metadata = {
            "genelist": genelist_id,
            "genelist_status": "Active" if new_status else "Inactive",
        }
        flash(
            f"Genelist: '{genelist_id}' is now {'active' if new_status else 'inactive'}.",
            "green",
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle genelist: {exc}", "red")
    return redirect(url_for("admin_bp.manage_genelists"))


@admin_bp.route("/genelists/<genelist_id>/delete", methods=["GET"])
@require("delete_isgl", min_role="admin", min_level=99999)
@log_action(action_name="delete_genelist", call_type="admin_call")
def delete_genelist(genelist_id: str) -> Response:
    try:
        get_web_api_client().delete_admin_genelist(
            genelist_id=genelist_id,
            headers=build_forward_headers(request.headers),
        )
        g.audit_metadata = {"genelist": genelist_id}
        flash(f"Genelist '{genelist_id}' deleted successfully!", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete genelist: {exc}", "red")
    return redirect(url_for("admin_bp.manage_genelists"))


@admin_bp.route("/genelists/<genelist_id>/view", methods=["GET"])
@require("view_isgl", min_role="user", min_level=9)
def view_genelist(genelist_id: str) -> Response | str:
    selected_assay = request.args.get("assay")
    try:
        view_context = get_web_api_client().get_admin_genelist_view_context(
            genelist_id=genelist_id,
            selected_assay=selected_assay,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash(f"Genelist '{genelist_id}' not found!", "red")
            return redirect(url_for("admin_bp.manage_genelists"))
        flash(f"Failed to load genelist view context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    genelist = view_context.genelist

    selected_version = request.args.get("version", type=int)
    delta = None
    if selected_version and selected_version != genelist.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(genelist.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = genelist["version_history"][version_index].get("delta", {})
            delta = delta_blob
            genelist = util.admin.apply_version_delta(deepcopy(genelist), delta_blob)

    filtered_genes = view_context.filtered_genes
    panel_germline_genes = view_context.panel_germline_genes

    return render_template(
        "isgl/view_isgl.html",
        genelist=genelist,
        selected_assay=selected_assay,
        filtered_genes=filtered_genes,
        is_public=False,
        selected_version=selected_version or genelist.get("version"),
        panel_germline_genes=panel_germline_genes,
        delta=delta,
    )
