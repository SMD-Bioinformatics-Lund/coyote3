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
from coyote.extensions import store, util
from coyote.services.audit_logs.decorators import log_action
from coyote.services.auth.decorators import require
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@admin_bp.route("/genelists", methods=["GET"])
@require("view_isgl", min_role="user", min_level=9)
def manage_genelists() -> str:
    genelists = store.isgl_handler.get_all_isgl()
    return render_template("isgl/manage_isgl.html", genelists=genelists, is_public=False)


@admin_bp.route("/genelists/new", methods=["GET", "POST"])
@require("create_isgl", min_role="manager", min_level=99)
@log_action(action_name="create_genelist", call_type="manager_call")
def create_genelist() -> Response | str:
    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="isgl_config",
        schema_category="ISGL",
        is_active=True,
    )

    if not active_schemas:
        flash("No active genelist schemas found!", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("Genelist schema not found!", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    assay_groups: list = store.asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["options"] = assay_groups

    assay_groups_panels = store.asp_handler.get_all_asps()
    assay_group_map = {}
    for _assay in assay_groups_panels:
        group = _assay.get("asp_group")
        if group not in assay_group_map:
            assay_group_map[group] = []

        group_map = {
            "assay_name": _assay.get("assay_name"),
            "display_name": _assay.get("display_name"),
            "asp_category": _assay.get("asp_category"),
        }
        assay_group_map[group].append(group_map)

    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

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
        selected_schema=schema,
        assay_group_map=assay_group_map,
    )


@admin_bp.route("/genelists/<genelist_id>/edit", methods=["GET", "POST"])
@require("edit_isgl", min_role="manager", min_level=99)
@log_action(action_name="edit_genelist", call_type="manager_call")
def edit_genelist(genelist_id: str) -> Response | str:
    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        flash("Genelist not found!", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    schema = store.schema_handler.get_schema(genelist.get("schema_name"))

    assay_groups = store.asp_handler.get_all_asp_groups()
    schema["fields"]["assay_groups"]["options"] = assay_groups
    schema["fields"]["assay_groups"]["default"] = genelist.get("assay_groups", [])

    assay_groups_panels = store.asp_handler.get_all_asps()
    assay_group_map = {}
    for _assay in assay_groups_panels:
        group = _assay.get("asp_group")
        if group not in assay_group_map:
            assay_group_map[group] = []

        group_map = {
            "assay_name": _assay.get("assay_name"),
            "display_name": _assay.get("display_name"),
            "asp_category": _assay.get("asp_category"),
        }
        assay_group_map[group].append(group_map)

    schema["fields"]["assays"]["default"] = genelist.get("assays", [])

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
    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        return abort(404)

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
    genelist = store.isgl_handler.get_isgl(genelist_id)
    if not genelist:
        flash(f"Genelist '{genelist_id}' not found!", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

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

    selected_assay = request.args.get("assay")
    all_genes = genelist.get("genes", [])
    assays = genelist.get("assays", [])

    filtered_genes = all_genes
    panel_germline_genes = []
    if selected_assay and selected_assay in assays:
        panel = store.asp_handler.get_asp(selected_assay)
        panel_genes = panel.get("covered_genes", []) if panel else []
        panel_germline_genes = panel.get("germline_genes", []) if panel else []
        filtered_genes = sorted(set(all_genes).intersection(panel_genes))

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
