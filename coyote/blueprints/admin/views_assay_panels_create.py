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

"""Admin assay panel creation routes (`/asp/new`)."""

from copy import deepcopy

from flask import Response, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


@admin_bp.route("/asp/new", methods=["GET", "POST"])
@log_action(action_name="create_asp", call_type="manager_call")
@login_required
def create_assay_panel():
    try:
        selected_schema_id = request.args.get("schema_id")
        context = get_web_api_client().get_json(
            api_endpoints.admin("asp", "create_context"),
            headers=forward_headers(),
            params={"schema_id": selected_schema_id} if selected_schema_id else None,
        )
    except ApiRequestError as exc:
        flash(f"Failed to load panel create context: {exc}", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    active_schemas = context.schemas
    schema = context.schema_payload

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
            get_web_api_client().post_json(
                api_endpoints.admin("asp", "create"),
                headers=forward_headers(),
                json_body={"config": config},
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
