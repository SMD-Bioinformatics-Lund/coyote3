"""Admin assay-configuration routes."""

from __future__ import annotations

import json

from flask import Response, abort, g, jsonify, redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import (
    api_page_guard,
    flash_api_failure,
    flash_api_success,
)


def _load_assay_context(assay_id: str):
    """Load assay-configuration context for edit, view, and print screens.

    Args:
        assay_id: Assay-configuration identifier.

    Returns:
        The decoded API context payload for the assay configuration.
    """
    with api_page_guard(
        logger=app.logger,
        log_message=f"Failed to load assay config context for {assay_id}",
        summary="Unable to load the assay configuration.",
        not_found_summary="Assay configuration not found.",
    ):
        return get_web_api_client().get_json(
            api_endpoints.admin("aspc", assay_id, "context"),
            headers=forward_headers(),
        )


def _apply_selected_assay_version(
    assay_config: dict, selected_version: int | None, assay_id: str, keep_version: bool = False
) -> tuple[dict, dict | None]:
    """Return the selected historical assay-config version for diff-aware rendering."""
    from coyote.util.admin_utility import apply_selected_version

    return apply_selected_version(
        assay_config, selected_version, id_field="_id", id_value=assay_id, keep_version=keep_version
    )


def _render_create_form(category: str) -> Response | str:
    """Render and submit the create form for a DNA or RNA assay configuration.

    Args:
        category: Assay category, typically ``DNA`` or ``RNA``.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    with api_page_guard(
        logger=app.logger,
        log_message=f"Failed to load {category} assay config create context",
        summary=f"Unable to load the {category} assay configuration form.",
    ):
        params = {"category": category}
        context = get_web_api_client().get_json(
            api_endpoints.admin("aspc", "create_context"),
            headers=forward_headers(),
            params=params,
        )

    if request.method == "POST":
        form_data = {
            key: (vals[0] if len(vals) == 1 else vals)
            for key, vals in request.form.to_dict(flat=False).items()
        }
        if category == "DNA":
            form_data["verification_samples"] = json.loads(
                request.form.get("verification_samples", "{}")
            )

        config = util.admin.process_form_to_config(form_data, context.form)
        config.update(
            {
                "_id": f"{config['assay_name']}:{config['environment']}",
            }
        )

        try:
            get_web_api_client().post_json(
                api_endpoints.admin("aspc"),
                headers=forward_headers(),
                json_body={"config": config},
            )
            flash_api_success(
                f"{config['assay_name']} : {config['environment']} assay config created."
            )
        except ApiRequestError as exc:
            flash_api_failure("Failed to create assay configuration.", exc)

        g.audit_metadata = {
            "assay": config["assay_name"],
            "environment": config["environment"],
        }
        return redirect(url_for("admin_bp.assay_configs"))

    return render_template(
        "aspc/create_aspc.html",
        schema=context.form,
        category=category,
        prefill_map_json=json.dumps(context.prefill_map),
    )


@admin_bp.route("/aspc/validate_aspc_id", methods=["POST"])
@login_required
def validate_aspc_id() -> Response:
    """Validate whether an aspc_id already exists."""
    body = request.json or {}
    aspc_id = str(body.get("aspc_id", "")).strip()
    assay_name = str(body.get("assay_name", "")).strip()
    environment = str(body.get("environment", "")).strip()
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("aspc", "validate_aspc_id"),
            headers=forward_headers(),
            json_body={
                "aspc_id": aspc_id,
                "assay_name": assay_name,
                "environment": environment,
            },
        )
        return jsonify({"exists": bool(payload.get("exists", False))})
    except ApiRequestError as exc:
        return jsonify({"exists": False, "error": str(exc)}), 502


@admin_bp.route("/aspc")
@login_required
def assay_configs() -> str:
    """Render the assay-configuration management page.

    Returns:
        The rendered management page response.
    """
    q = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    per_page = max(1, min(request.args.get("per_page", default=30, type=int) or 30, 200))
    with api_page_guard(
        logger=app.logger,
        log_message="Failed to fetch assay configs",
        summary="Unable to load assay configurations.",
    ):
        payload = get_web_api_client().get_json(
            api_endpoints.admin("aspc"),
            headers=forward_headers(),
            params={"q": q, "page": page, "per_page": per_page},
        )
        assay_configs = payload.assay_configs
        pagination = payload.get("pagination", {})
    return render_template(
        "aspc/manage_aspc.html",
        assay_configs=assay_configs,
        q=q,
        page=pagination.get("page", page),
        per_page=pagination.get("per_page", per_page),
        total=pagination.get("total", 0),
        has_next=pagination.get("has_next", False),
    )


@admin_bp.route("/aspc/dna/new", methods=["GET", "POST"])
@login_required
def create_dna_assay_config() -> Response | str:
    """Create a DNA assay configuration.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    return _render_create_form("DNA")


@admin_bp.route("/aspc/rna/new", methods=["GET", "POST"])
@login_required
def create_rna_assay_config() -> Response | str:
    """Create an RNA assay configuration.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    return _render_create_form("RNA")


@admin_bp.route("/aspc/<assay_id>/edit", methods=["GET", "POST"])
@login_required
def edit_assay_config(assay_id: str) -> Response | str:
    """Edit an assay configuration.

    Args:
        assay_id: Assay-configuration identifier for the document being edited.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    context = _load_assay_context(assay_id)

    selected_version = request.args.get("version", type=int)
    assay_config, delta = _apply_selected_assay_version(
        context.assay_config, selected_version, assay_id
    )

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

        updated_config = util.admin.process_form_to_config(form_data, context.form)
        updated_config["_id"] = assay_config.get("_id")
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
            flash_api_success("Assay configuration updated successfully.")
        except ApiRequestError as exc:
            flash_api_failure("Failed to update assay configuration.", exc)
        return redirect(url_for("admin_bp.assay_configs"))

    return render_template(
        "aspc/edit_aspc.html",
        schema=context.form,
        assay_config=assay_config,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/aspc/<assay_id>/view", methods=["GET"])
@login_required
def view_assay_config(assay_id: str) -> str | Response:
    """Display a read-only assay configuration view.

    Args:
        assay_id: Assay-configuration identifier for the document being displayed.

    Returns:
        The rendered detail page response.
    """
    context = _load_assay_context(assay_id)

    selected_version = request.args.get("version", type=int)
    assay_config, delta = _apply_selected_assay_version(
        context.assay_config, selected_version, assay_id
    )

    return render_template(
        "aspc/view_aspc.html",
        schema=context.form,
        assay_config=assay_config,
        selected_version=selected_version or assay_config.get("version"),
        delta=delta,
    )


@admin_bp.route("/aspc/<assay_id>/print", methods=["GET"])
@login_required
def print_assay_config(assay_id: str) -> str | Response:
    """Render a print-friendly assay configuration view.

    Args:
        assay_id: Assay-configuration identifier for the document being printed.

    Returns:
        The rendered print view response.
    """
    context = _load_assay_context(assay_id)

    selected_version = request.args.get("version", type=int)
    assay_config, _ = _apply_selected_assay_version(
        context.assay_config, selected_version, assay_id, keep_version=True
    )

    return render_template(
        "aspc/print_aspc.html",
        schema=context.form,
        config=assay_config,
        now=util.common.utc_now(),
        selected_version=selected_version,
    )


@admin_bp.route("/aspc/<assay_id>/toggle", methods=["POST", "GET"])
@login_required
def toggle_assay_config_active(assay_id: str) -> Response:
    """Toggle the active flag on an assay configuration.

    Args:
        assay_id: Assay-configuration identifier for the document being updated.

    Returns:
        A redirect response back to the management page.
    """
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
        flash_api_success(
            f"Assay config '{assay_id}' is now {'active' if new_status else 'inactive'}."
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash_api_failure("Failed to update assay configuration status.", exc)
    return redirect(url_for("admin_bp.assay_configs"))


@admin_bp.route("/aspc/<assay_id>/delete", methods=["GET"])
@login_required
def delete_assay_config(assay_id: str) -> Response:
    """Delete an assay configuration.

    Args:
        assay_id: Assay-configuration identifier for the document being deleted.

    Returns:
        A redirect response back to the management page.
    """
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("aspc", assay_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"assay": assay_id}
        flash_api_success(f"Assay config '{assay_id}' deleted successfully.")
    except ApiRequestError as exc:
        flash_api_failure("Failed to delete assay configuration.", exc)
    return redirect(url_for("admin_bp.assay_configs"))
