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

from flask import current_app as app
from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user

from coyote.blueprints.admin import admin_bp
from coyote.extensions import store, util
from coyote.services.audit_logs.decorators import log_action
from coyote.services.auth.decorators import require
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@admin_bp.route("/aspc")
@require("view_aspc", min_role="user", min_level=9)
def assay_configs() -> str:
    assay_configs = store.aspc_handler.get_all_aspc()
    return render_template("aspc/manage_aspc.html", assay_configs=assay_configs)


@admin_bp.route("/aspc/dna/new", methods=["GET", "POST"])
@require("create_aspc", min_role="manager", min_level=99)
@log_action(action_name="create_assay_config", call_type="manager_call")
def create_dna_assay_config() -> Response | str:
    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="asp_config", schema_category="DNA", is_active=True
    )

    if not active_schemas:
        flash("No active DNA schemas found!", "red")
        return redirect(url_for("admin_bp.aspc"))

    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("Selected schema not found!", "red")
        return redirect(url_for("admin_bp.aspc"))

    assay_panels = store.asp_handler.get_all_asps(is_active=True)
    prefill_map = {}
    valid_assay_ids = []

    for p in assay_panels:
        if p.get("asp_category") == "DNA":
            envs = store.aspc_handler.get_available_assay_envs(
                p["_id"], schema["fields"]["environment"]["options"]
            )
            if envs:
                valid_assay_ids.append(p["_id"])
                prefill_map[p["_id"]] = {
                    "display_name": p.get("display_name"),
                    "asp_group": p.get("asp_group"),
                    "asp_category": p.get("asp_category"),
                    "platform": p.get("platform"),
                    "environment": envs,
                }

    schema["fields"]["assay_name"]["options"] = valid_assay_ids
    schema["fields"]["vep_consequences"]["options"] = list(
        app.config.get("CONSEQ_TERMS_MAPPER", {}).keys()
    )
    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

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

        existing_config = store.aspc_handler.get_aspc_with_id(config["_id"])
        if existing_config:
            flash(
                f"Assay config '{config['assay_name']} for {config['environment']}' already exists!",
                "red",
            )
        else:
            try:
                get_web_api_client().create_admin_aspc(
                    config=config,
                    headers=build_forward_headers(request.headers),
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
        selected_schema=schema,
        prefill_map_json=json.dumps(prefill_map),
    )


@admin_bp.route("/aspc/rna/new", methods=["GET", "POST"])
@require("create_aspc", min_role="manager", min_level=99)
@log_action(action_name="create_assay_config", call_type="manager_call")
def create_rna_assay_config() -> Response | str:
    active_schemas = store.schema_handler.get_schemas_by_category_type(
        schema_type="asp_config", schema_category="RNA", is_active=True
    )

    if not active_schemas:
        flash("No active RNA schemas found!", "red")
        return redirect(url_for("admin_bp.aspc"))

    selected_id = request.args.get("schema_id") or active_schemas[0]["_id"]
    schema = next((s for s in active_schemas if s["_id"] == selected_id), None)

    if not schema:
        flash("Selected schema not found!", "red")
        return redirect(url_for("admin_bp.aspc"))

    assay_panels = store.asp_handler.get_all_asps(is_active=True)
    prefill_map = {}
    valid_assay_ids = []

    for p in assay_panels:
        if p.get("asp_category") == "RNA":
            envs = store.aspc_handler.get_available_assay_envs(
                p["_id"], schema["fields"]["environment"]["options"]
            )
            if envs:
                valid_assay_ids.append(p["_id"])
                prefill_map[p["_id"]] = {
                    "display_name": p.get("display_name"),
                    "asp_group": p.get("asp_group"),
                    "asp_category": p.get("asp_category"),
                    "platform": p.get("platform"),
                    "environment": envs,
                }

    schema["fields"]["assay_name"]["options"] = valid_assay_ids
    schema["fields"]["created_by"]["default"] = current_user.email
    schema["fields"]["created_on"]["default"] = util.common.utc_now()
    schema["fields"]["updated_by"]["default"] = current_user.email
    schema["fields"]["updated_on"]["default"] = util.common.utc_now()

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

        existing_config = store.aspc_handler.get_aspc_with_id(config["_id"])
        if existing_config:
            flash(
                f"Assay config '{config['assay_name']} for {config['environment']}' already exists!",
                "red",
            )
        else:
            try:
                get_web_api_client().create_admin_aspc(
                    config=config,
                    headers=build_forward_headers(request.headers),
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
        selected_schema=schema,
        prefill_map_json=json.dumps(prefill_map),
    )


@admin_bp.route("/aspc/<assay_id>/edit", methods=["GET", "POST"])
@require("edit_aspc", min_role="manager", min_level=99)
@log_action(action_name="edit_assay_config", call_type="developer_call")
def edit_assay_config(assay_id: str) -> Response | str:
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        flash("Assay config not found.", "red")
        return redirect(url_for("admin_bp.aspc"))

    schema = store.schema_handler.get_schema(assay_config.get("schema_name"))
    if not schema:
        flash("Schema for this assay config is missing.", "red")
        return redirect(url_for("admin_bp.aspc"))

    vep_terms = list(app.config.get("CONSEQ_TERMS_MAPPER", {}).keys())
    if "vep_consequences" in schema["fields"]:
        schema["fields"]["vep_consequences"]["options"] = vep_terms

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
            get_web_api_client().update_admin_aspc(
                assay_id=assay_id,
                config=updated_config,
                headers=build_forward_headers(request.headers),
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
@require("view_aspc", min_role="user", min_level=9)
@log_action(action_name="view_assay_config", call_type="viewer_call")
def view_assay_config(assay_id: str) -> str | Response:
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        flash("Assay config not found.", "red")
        return redirect(url_for("admin_bp.aspc"))

    schema = store.schema_handler.get_schema(assay_config.get("schema_name"))
    if not schema:
        flash("Schema for this assay config is missing.", "red")
        return redirect(url_for("admin_bp.aspc"))

    if "vep_consequences" in schema["fields"]:
        schema["fields"]["vep_consequences"]["options"] = list(
            app.config.get("CONSEQ_TERMS_MAPPER", {}).keys()
        )

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
@require("view_aspc", min_role="user", min_level=9)
@log_action(action_name="print_assay_config", call_type="viewer_call")
def print_assay_config(assay_id: str) -> str | Response:
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        flash("Assay config not found.", "red")
        return redirect(url_for("admin_bp.aspc"))

    schema = store.schema_handler.get_schema(assay_config.get("schema_name"))
    if not schema:
        flash("Schema not found for assay config.", "red")
        return redirect(url_for("admin_bp.aspc"))

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
@require("edit_aspc", min_role="manager", min_level=99)
@log_action(action_name="edit_assay_config", call_type="developer_call")
def toggle_assay_config_active(assay_id: str) -> Response:
    assay_config = store.aspc_handler.get_aspc_with_id(assay_id)
    if not assay_config:
        return abort(404)

    try:
        payload = get_web_api_client().toggle_admin_aspc(
            assay_id=assay_id,
            headers=build_forward_headers(request.headers),
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
        flash(f"Failed to toggle assay config: {exc}", "red")
    return redirect(url_for("admin_bp.assay_configs"))


@admin_bp.route("/aspc/<assay_id>/delete", methods=["GET"])
@require("delete_aspc", min_role="admin", min_level=99999)
@log_action(action_name="delete_assay_config", call_type="admin_call")
def delete_assay_config(assay_id: str) -> Response:
    try:
        get_web_api_client().delete_admin_aspc(
            assay_id=assay_id,
            headers=build_forward_headers(request.headers),
        )
        g.audit_metadata = {"assay": assay_id}
        flash(f"Assay config '{assay_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete assay config: {exc}", "red")
    return redirect(url_for("admin_bp.assay_configs"))
