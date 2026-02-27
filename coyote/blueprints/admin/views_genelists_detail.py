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

"""Admin in-silico genelist edit/view routes."""

from copy import deepcopy

from flask import Response, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


def _extract_genes_from_request(
    form_data: dict[str, list[str] | str], fallback_genes: list[str]
) -> list[str]:
    genes: list[str] = []
    if "genes_file" in request.files and request.files["genes_file"].filename:
        file = request.files["genes_file"]
        content = file.read().decode("utf-8")
        genes = [g.strip() for g in content.replace(",", "\n").splitlines() if g.strip()]
    elif "genes_paste" in form_data and form_data["genes_paste"].strip():
        pasted = form_data["genes_paste"].replace(",", "\n")
        genes = [g.strip() for g in pasted.splitlines() if g.strip()]
    else:
        genes = fallback_genes
    genes = list(set(deepcopy(genes)))
    genes.sort()
    return genes


def _apply_selected_version(
    genelist: dict, selected_version: int | None, genelist_id: str | None = None
) -> tuple[dict, dict | None]:
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
            if genelist_id:
                genelist["_id"] = genelist_id
    return genelist, delta


@admin_bp.route("/genelists/<genelist_id>/edit", methods=["GET", "POST"])
@log_action(action_name="edit_genelist", call_type="manager_call")
@login_required
def edit_genelist(genelist_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("genelists", genelist_id, "context"),
            headers=forward_headers(),
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
    genelist, delta = _apply_selected_version(genelist, selected_version, genelist_id)

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
        genes = _extract_genes_from_request(form_data, genelist.get("genes", []))

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
            get_web_api_client().post_json(
                api_endpoints.admin("genelists", genelist_id, "update"),
                headers=forward_headers(),
                json_body={"config": updated},
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


@admin_bp.route("/genelists/<genelist_id>/view", methods=["GET"])
@login_required
def view_genelist(genelist_id: str) -> Response | str:
    selected_assay = request.args.get("assay")
    try:
        view_context = get_web_api_client().get_json(
            api_endpoints.admin("genelists", genelist_id, "view_context"),
            headers=forward_headers(),
            params={"assay": selected_assay} if selected_assay else None,
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash(f"Genelist '{genelist_id}' not found!", "red")
            return redirect(url_for("admin_bp.manage_genelists"))
        flash(f"Failed to load genelist view context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_genelists"))

    genelist = view_context.genelist
    selected_version = request.args.get("version", type=int)
    genelist, delta = _apply_selected_version(genelist, selected_version)

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
