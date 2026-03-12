"""Admin assay-configuration routes."""

from __future__ import annotations

import json
from copy import deepcopy

from flask import Response, abort, flash, g, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)


def _load_assay_context(assay_id: str):
    try:
        return get_web_api_client().get_json(
            api_endpoints.admin("aspc", assay_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        flash("Assay config not found." if exc.status_code == 404 else f"Failed to load assay config context: {exc}", "red")
        return None


def _apply_selected_assay_version(
    assay_config: dict, selected_version: int | None, assay_id: str, keep_version: bool = False
) -> tuple[dict, dict | None]:
    delta = None
    if selected_version and selected_version != assay_config.get("version"):
        version_index = next(
            (
                i
                for i, version_entry in enumerate(assay_config.get("version_history", []))
                if version_entry["version"] == selected_version + 1
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

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        if category == "DNA":
            form_data["verification_samples"] = json.loads(request.form.get("verification_samples", "{}"))
            form_data["query"] = json.loads(request.form.get("query", "{}"))

        config = util.admin.process_form_to_config(form_data, context.schema)
        config.update(
            {
                "_id": f"{config['assay_name']}:{config['environment']}",
                "schema_name": context.schema["_id"],
                "schema_version": context.schema["version"],
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
                api_endpoints.admin("aspc"),
                headers=forward_headers(),
                json_body={"config": config},
            )
            flash(f"{config['assay_name']} : {config['environment']} assay config created!", "green")
        except ApiRequestError as exc:
            flash(f"Failed to create assay config: {exc}", "red")

        g.audit_metadata = {
            "assay": config["assay_name"],
            "environment": config["environment"],
        }
        return redirect(url_for("admin_bp.assay_configs"))

    return render_template(
        "aspc/create_aspc.html",
        schema=context.schema,
        schemas=context.schemas,
        selected_schema=context.selected_schema,
        prefill_map_json=json.dumps(context.prefill_map),
    )


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
@login_required
def create_dna_assay_config() -> Response | str:
    return _render_create_form("DNA")


@admin_bp.route("/aspc/rna/new", methods=["GET", "POST"])
@login_required
def create_rna_assay_config() -> Response | str:
    return _render_create_form("RNA")


@admin_bp.route("/aspc/<assay_id>/edit", methods=["GET", "POST"])
@login_required
def edit_assay_config(assay_id: str) -> Response | str:
    context = _load_assay_context(assay_id)
    if context is None:
        return redirect(url_for("admin_bp.assay_configs"))

    selected_version = request.args.get("version", type=int)
    assay_config, delta = _apply_selected_assay_version(context.assay_config, selected_version, assay_id)

    if request.method == "POST":
        form_data = {
            key: (request.form.getlist(key) if len(request.form.getlist(key)) > 1 else request.form[key])
            for key in request.form
        }
        form_data["verification_samples"] = util.common.safe_json_load(
            request.form.get("verification_samples", "{}")
        )
        form_data["query"] = util.common.safe_json_load(request.form.get("query", "{}"))

        updated_config = util.admin.process_form_to_config(form_data, context.schema)
        updated_config["_id"] = assay_config.get("_id")
        updated_config["updated_on"] = util.common.utc_now()
        updated_config["updated_by"] = current_user.email
        updated_config["schema_name"] = context.schema["_id"]
        updated_config["schema_version"] = context.schema["version"]
        updated_config["version"] = assay_config.get("version", 1) + 1
        updated_config = util.admin.inject_version_history(
            user_email=current_user.email,
            new_config=updated_config,
            old_config=assay_config,
            is_new=False,
        )
        try:
            get_web_api_client().put_json(
                api_endpoints.admin("aspc", assay_id),
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
        schema=context.schema,
        assay_config=assay_config,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/aspc/<assay_id>/view", methods=["GET"])
@login_required
def view_assay_config(assay_id: str) -> str | Response:
    context = _load_assay_context(assay_id)
    if context is None:
        return redirect(url_for("admin_bp.assay_configs"))

    selected_version = request.args.get("version", type=int)
    assay_config, delta = _apply_selected_assay_version(context.assay_config, selected_version, assay_id)

    return render_template(
        "aspc/view_aspc.html",
        schema=context.schema,
        assay_config=assay_config,
        selected_version=selected_version or assay_config.get("version"),
        delta=delta,
    )


@admin_bp.route("/aspc/<assay_id>/print", methods=["GET"])
@login_required
def print_assay_config(assay_id: str) -> str | Response:
    context = _load_assay_context(assay_id)
    if context is None:
        return redirect(url_for("admin_bp.assay_configs"))

    selected_version = request.args.get("version", type=int)
    assay_config, _ = _apply_selected_assay_version(
        context.assay_config, selected_version, assay_id, keep_version=True
    )

    return render_template(
        "aspc/print_aspc.html",
        schema=context.schema,
        config=assay_config,
        now=util.common.utc_now(),
        selected_version=selected_version,
    )


@admin_bp.route("/aspc/<assay_id>/toggle", methods=["POST", "GET"])
@login_required
def toggle_assay_config_active(assay_id: str) -> Response:
    try:
        payload = get_web_api_client().patch_json(
            api_endpoints.admin("aspc", assay_id, "status"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", True))
        g.audit_metadata = {
            "assay": assay_id,
            "assay_status": "Active" if new_status else "Inactive",
        }
        flash(f"Assay config '{assay_id}' is now {'active' if new_status else 'inactive'}.", "green")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash(f"Failed to toggle assay config: {exc}", "red")
    return redirect(url_for("admin_bp.assay_configs"))


@admin_bp.route("/aspc/<assay_id>/delete", methods=["GET"])
@login_required
def delete_assay_config(assay_id: str) -> Response:
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("aspc", assay_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"assay": assay_id}
        flash(f"Assay config '{assay_id}' deleted successfully.", "green")
    except ApiRequestError as exc:
        flash(f"Failed to delete assay config: {exc}", "red")
    return redirect(url_for("admin_bp.assay_configs"))
