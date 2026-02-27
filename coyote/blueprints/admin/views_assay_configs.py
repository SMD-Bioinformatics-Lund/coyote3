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

"""Admin assay configuration routes (`/aspc/*`)."""

from copy import deepcopy
import json

from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.services.audit_logs.decorators import log_action
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


@admin_bp.route("/aspc")
@login_required
def assay_configs() -> str:
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("aspc"),
            headers=forward_headers(),
        )
        assay_configs = payload.assay_configs
    except ApiRequestError as exc:
        flash(f"Failed to fetch assay configs: {exc}", "red")
        assay_configs = []
    return render_template("aspc/manage_aspc.html", assay_configs=assay_configs)


@admin_bp.route("/aspc/dna/new", methods=["GET", "POST"])
@log_action(action_name="create_assay_config", call_type="manager_call")
@login_required
def create_dna_assay_config() -> Response | str:
    try:
        selected_schema_id = request.args.get("schema_id")
        params = {"category": "DNA"}
        if selected_schema_id:
            params["schema_id"] = selected_schema_id
        context = get_web_api_client().get_json(
            api_endpoints.admin("aspc", "create_context"),
            headers=forward_headers(),
            params=params,
        )
    except ApiRequestError as exc:
        flash(f"Failed to load DNA assay config context: {exc}", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    active_schemas = context.schemas
    schema = context.schema_payload
    prefill_map = context.prefill_map

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        form_data["verification_samples"] = json.loads(request.form.get("verification_samples", "{}"))
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


@admin_bp.route("/aspc/rna/new", methods=["GET", "POST"])
@log_action(action_name="create_assay_config", call_type="manager_call")
@login_required
def create_rna_assay_config() -> Response | str:
    try:
        selected_schema_id = request.args.get("schema_id")
        params = {"category": "RNA"}
        if selected_schema_id:
            params["schema_id"] = selected_schema_id
        context = get_web_api_client().get_json(
            api_endpoints.admin("aspc", "create_context"),
            headers=forward_headers(),
            params=params,
        )
    except ApiRequestError as exc:
        flash(f"Failed to load RNA assay config context: {exc}", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    active_schemas = context.schemas
    schema = context.schema_payload
    prefill_map = context.prefill_map

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }

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


@admin_bp.route("/aspc/<assay_id>/edit", methods=["GET", "POST"])
@log_action(action_name="edit_assay_config", call_type="developer_call")
@login_required
def edit_assay_config(assay_id: str) -> Response | str:
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("aspc", assay_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("Assay config not found.", "red")
        else:
            flash(f"Failed to load assay config context: {exc}", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    assay_config = context.assay_config
    schema = context.schema_payload

    selected_version = request.args.get("version", type=int)
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
            delta = delta_blob
            assay_config["_id"] = assay_id

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
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("aspc", assay_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("Assay config not found.", "red")
        else:
            flash(f"Failed to load assay config context: {exc}", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    assay_config = context.assay_config
    schema = context.schema_payload

    selected_version = request.args.get("version", type=int)
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
            delta = delta_blob

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
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("aspc", assay_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            flash("Assay config not found.", "red")
        else:
            flash(f"Failed to load assay config context: {exc}", "red")
        return redirect(url_for("admin_bp.assay_configs"))

    assay_config = context.assay_config
    schema = context.schema_payload

    selected_version = request.args.get("version", type=int)
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
            assay_config["version"] = selected_version

    return render_template(
        "aspc/print_aspc.html",
        schema=schema,
        config=assay_config,
        now=util.common.utc_now(),
        selected_version=selected_version,
    )


@admin_bp.route("/aspc/<assay_id>/toggle", methods=["POST", "GET"])
@log_action(action_name="edit_assay_config", call_type="developer_call")
@login_required
def toggle_assay_config_active(assay_id: str) -> Response:
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("aspc", assay_id, "toggle"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", False))
        g.audit_metadata = {
            "assay": assay_id,
            "assay_status": "Active" if new_status else "Inactive",
        }
        flash(
            f"Assay config '{assay_id}' is now {'active' if new_status else 'inactive'}.",
            "green",
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle assay config: {exc}", "red")
    return redirect(url_for("admin_bp.assay_configs"))


@admin_bp.route("/aspc/<assay_id>/delete", methods=["GET"])
@log_action(action_name="delete_assay_config", call_type="admin_call")
@login_required
def delete_assay_config(assay_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            api_endpoints.admin("aspc", assay_id, "delete"),
            headers=forward_headers(),
        )
        g.audit_metadata = {"assay": assay_id}
        flash(f"Assay config '{assay_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete assay config: {exc}", "red")
    return redirect(url_for("admin_bp.assay_configs"))
