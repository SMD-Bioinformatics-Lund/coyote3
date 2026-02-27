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

"""Admin assay panel detail routes (`edit/view/print`)."""

from copy import deepcopy

from flask import Response, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


def _load_panel_context(assay_panel_id: str):
    try:
        return get_web_api_client().get_json(
            api_endpoints.admin("asp", assay_panel_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("Panel or schema not found.", "red")
        else:
            flash(f"Failed to load panel context: {exc}", "red")
        return None


def _apply_selected_version(
    panel: dict, selected_version: int | None, panel_id: str, keep_version: bool = False
) -> tuple[dict, dict | None]:
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
            panel = util.admin.apply_version_delta(
                deepcopy(panel) if keep_version else panel,
                delta_blob,
            )
            delta = delta_blob
            panel["_id"] = panel_id
            if keep_version:
                panel["version"] = selected_version
    return panel, delta


@admin_bp.route("/asp/<assay_panel_id>/edit", methods=["GET", "POST"])
@log_action(action_name="edit_asp", call_type="manager_call")
@login_required
def edit_assay_panel(assay_panel_id: str) -> str | Response:
    context = _load_panel_context(assay_panel_id)
    if context is None:
        return redirect(url_for("admin_bp.manage_assay_panels"))

    panel = context.panel
    schema = context.schema_payload

    selected_version = request.args.get("version", type=int)
    panel, delta = _apply_selected_version(panel, selected_version, assay_panel_id)

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
        if "genes_file" not in request.files and "genes_paste" not in form_data:
            covered_genes = panel.get("covered_genes", [])

        germline_genes = util.admin.extract_gene_list(
            request.files.get("germline_genes_file"),
            form_data.get("germline_genes_paste", ""),
        )
        if "germline_genes_file" not in request.files and "germline_genes_paste" not in form_data:
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
            get_web_api_client().post_json(
                api_endpoints.admin("asp", assay_panel_id, "update"),
                headers=forward_headers(),
                json_body={"config": updated},
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
@login_required
def view_assay_panel(assay_panel_id: str) -> Response | str:
    context = _load_panel_context(assay_panel_id)
    if context is None:
        return redirect(url_for("admin_bp.manage_assay_panels"))

    panel = context.panel
    schema = context.schema_payload
    selected_version = request.args.get("version", type=int)
    panel, delta = _apply_selected_version(panel, selected_version, assay_panel_id)

    return render_template(
        "asp/view_asp.html",
        panel=panel,
        schema=schema,
        selected_version=selected_version or panel.get("version"),
        delta=delta,
    )


@admin_bp.route("/asp/<panel_id>/print", methods=["GET"])
@log_action(action_name="print_asp", call_type="viewer_call")
@login_required
def print_assay_panel(panel_id: str) -> str | Response:
    context = _load_panel_context(panel_id)
    if context is None:
        return redirect(url_for("admin_bp.manage_assay_panels"))

    panel = context.panel
    schema = context.schema_payload

    selected_version = request.args.get("version", type=int)
    panel, _ = _apply_selected_version(panel, selected_version, panel_id, keep_version=True)

    return render_template(
        "asp/print_asp.html",
        schema=schema,
        config=panel,
        now=util.common.utc_now(),
        selected_version=selected_version,
    )
