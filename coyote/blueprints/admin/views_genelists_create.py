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

"""Admin in-silico genelist create routes."""

from copy import deepcopy

from flask import Response, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


def _extract_genes_from_request(form_data: dict[str, list[str] | str]) -> list[str]:
    genes: list[str] = []
    if "genes_file" in request.files and request.files["genes_file"].filename:
        file = request.files["genes_file"]
        content = file.read().decode("utf-8")
        genes = [g.strip() for g in content.replace(",", "\n").splitlines() if g.strip()]
    elif "genes_paste" in form_data and form_data["genes_paste"].strip():
        genes = [g.strip() for g in form_data["genes_paste"].replace(",", "\n").splitlines() if g.strip()]
    genes = list(set(deepcopy(genes)))
    genes.sort()
    return genes


@admin_bp.route("/genelists/new", methods=["GET", "POST"])
@log_action(action_name="create_genelist", call_type="manager_call")
@login_required
def create_genelist() -> Response | str:
    try:
        selected_schema_id = request.args.get("schema_id")
        context = get_web_api_client().get_json(
            api_endpoints.admin("genelists", "create_context"),
            headers=forward_headers(),
            params={"schema_id": selected_schema_id} if selected_schema_id else None,
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

        genes = _extract_genes_from_request(form_data)
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
            get_web_api_client().post_json(
                api_endpoints.admin("genelists", "create"),
                headers=forward_headers(),
                json_body={"config": config},
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
