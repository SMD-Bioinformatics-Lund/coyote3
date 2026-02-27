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

"""Admin assay configuration creation routes (`/aspc/*/new`)."""

from copy import deepcopy
import json

from flask import Response, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


def _render_create_form(category: str) -> Response | str:
    try:
        selected_schema_id = request.args.get("schema_id")
        params = {"category": category}
        if selected_schema_id:
            params["schema_id"] = selected_schema_id
        context = get_web_api_client().get_json(
            api_endpoints.admin("aspc", "create_context"),
            headers=forward_headers(),
            params=params,
        )
    except ApiRequestError as exc:
        flash(f"Failed to load {category} assay config context: {exc}", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    active_schemas = context.schemas
    schema = context.schema_payload
    prefill_map = context.prefill_map

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        if category == "DNA":
            form_data["verification_samples"] = json.loads(
                request.form.get("verification_samples", "{}")
            )
            form_data["query"] = json.loads(request.form.get("query", "{}"))

        config = util.admin.process_form_to_config(form_data, schema)
        config.update(
            {
                "_id": f"{config['assay_name']}:{config['environment']}",
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
                api_endpoints.admin("aspc", "create"),
                headers=forward_headers(),
                json_body={"config": config},
            )
            flash(
                f"{config['assay_name']} : {config['environment']} assay config created!",
                "green",
            )
        except ApiRequestError as exc:
            flash(f"Failed to create assay config: {exc}", "red")

        g.audit_metadata = {
            "assay": config["assay_name"],
            "environment": config["environment"],
        }
        return redirect(url_for("admin_bp.assay_configs"))

    return render_template(
        "aspc/create_aspc.html",
        schema=schema,
        schemas=active_schemas,
        selected_schema=context.selected_schema,
        prefill_map_json=json.dumps(prefill_map),
    )


@admin_bp.route("/aspc/dna/new", methods=["GET", "POST"])
@log_action(action_name="create_assay_config", call_type="manager_call")
@login_required
def create_dna_assay_config() -> Response | str:
    return _render_create_form("DNA")


@admin_bp.route("/aspc/rna/new", methods=["GET", "POST"])
@log_action(action_name="create_assay_config", call_type="manager_call")
@login_required
def create_rna_assay_config() -> Response | str:
    return _render_create_form("RNA")
