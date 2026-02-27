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

"""Admin assay configuration detail routes (`edit/view/print`)."""

from copy import deepcopy

from flask import Response, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.audit_logs.decorators import log_action


def _load_assay_context(assay_id: str):
    try:
        return get_web_api_client().get_json(
            api_endpoints.admin("aspc", assay_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("Assay config not found.", "red")
        else:
            flash(f"Failed to load assay config context: {exc}", "red")
        return None


def _apply_selected_version(
    assay_config: dict, selected_version: int | None, assay_id: str, keep_version: bool = False
) -> tuple[dict, dict | None]:
    delta = None
    if selected_version and selected_version != assay_config.get("version"):
        version_index = next(
            (
                i
                for i, v in enumerate(assay_config.get("version_history", []))
                if v["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = assay_config["version_history"][version_index].get("delta", {})
            assay_config = util.admin.apply_version_delta(deepcopy(assay_config), delta_blob)
            assay_config["_id"] = assay_id
            if keep_version:
                assay_config["version"] = selected_version
            delta = delta_blob
    return assay_config, delta


@admin_bp.route("/aspc/<assay_id>/edit", methods=["GET", "POST"])
@log_action(action_name="edit_assay_config", call_type="developer_call")
@login_required
def edit_assay_config(assay_id: str) -> Response | str:
    context = _load_assay_context(assay_id)
    if context is None:
        return redirect(url_for("admin_bp.assay_configs"))

    assay_config = context.assay_config
    schema = context.schema_payload

    selected_version = request.args.get("version", type=int)
    assay_config, delta = _apply_selected_version(assay_config, selected_version, assay_id)

    if request.method == "POST":
        form_data = {
            key: (
                request.form.getlist(key)
                if len(request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }
        form_data["verification_samples"] = util.common.safe_json_load(
            request.form.get("verification_samples", "{}")
        )
        form_data["query"] = util.common.safe_json_load(request.form.get("query", "{}"))

        updated_config = util.admin.process_form_to_config(form_data, schema)
        updated_config["_id"] = assay_config.get("_id")
        updated_config["updated_on"] = util.common.utc_now()
        updated_config["updated_by"] = current_user.email
        updated_config["schema_name"] = schema["_id"]
        updated_config["schema_version"] = schema["version"]
        updated_config["version"] = assay_config.get("version", 1) + 1

        updated_config = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=updated_config,
            old_config=assay_config,
            is_new=False,
        )

        try:
            get_web_api_client().post_json(
                api_endpoints.admin("aspc", assay_id, "update"),
                headers=forward_headers(),
                json_body={"config": updated_config},
            )
            g.audit_metadata = {
                "assay": updated_config.get("assay_name"),
                "environment": updated_config.get("environment"),
            }
            flash("Assay configuration updated successfully.", "green")
        except ApiRequestError as exc:
            flash(f"Failed to update assay config: {exc}", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    return render_template(
        "aspc/edit_aspc.html",
        schema=schema,
        assay_config=assay_config,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/aspc/<assay_id>/view", methods=["GET"])
@log_action(action_name="view_assay_config", call_type="viewer_call")
@login_required
def view_assay_config(assay_id: str) -> str | Response:
    context = _load_assay_context(assay_id)
    if context is None:
        return redirect(url_for("admin_bp.assay_configs"))

    assay_config = context.assay_config
    schema = context.schema_payload

    selected_version = request.args.get("version", type=int)
    assay_config, delta = _apply_selected_version(assay_config, selected_version, assay_id)

    return render_template(
        "aspc/view_aspc.html",
        schema=schema,
        assay_config=assay_config,
        selected_version=selected_version or assay_config.get("version"),
        delta=delta,
    )


@admin_bp.route("/aspc/<assay_id>/print", methods=["GET"])
@log_action(action_name="print_assay_config", call_type="viewer_call")
@login_required
def print_assay_config(assay_id: str) -> str | Response:
    context = _load_assay_context(assay_id)
    if context is None:
        return redirect(url_for("admin_bp.assay_configs"))

    assay_config = context.assay_config
    schema = context.schema_payload

    selected_version = request.args.get("version", type=int)
    assay_config, _ = _apply_selected_version(
        assay_config, selected_version, assay_id, keep_version=True
    )

    return render_template(
        "aspc/print_aspc.html",
        schema=schema,
        config=assay_config,
        now=util.common.utc_now(),
        selected_version=selected_version,
    )
