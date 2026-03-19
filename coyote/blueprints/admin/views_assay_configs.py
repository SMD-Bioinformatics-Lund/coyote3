"""Admin assay-configuration routes."""

from __future__ import annotations

import json
from copy import deepcopy

from flask import Response, abort, g, redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import current_user, login_required

from coyote.blueprints.admin import admin_bp
from coyote.extensions import util
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)
from coyote.services.api_client.web import (
    flash_api_failure,
    flash_api_success,
    raise_page_load_error,
)


def _load_assay_context(assay_id: str):
    """Load assay-configuration context for edit, view, and print screens.

    Args:
        assay_id: Assay-configuration identifier.

    Returns:
        The decoded API context payload for the assay configuration.
    """
    try:
        return get_web_api_client().get_json(
            api_endpoints.admin("aspc", assay_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load assay config context for {assay_id}",
            summary="Unable to load the assay configuration.",
            not_found_summary="Assay configuration not found.",
        )


def _apply_selected_assay_version(
    assay_config: dict, selected_version: int | None, assay_id: str, keep_version: bool = False
) -> tuple[dict, dict | None]:
    """Return the selected historical assay-config version for diff-aware rendering.

    Args:
        assay_config: Assay-configuration document returned by the API context
            endpoint.
        selected_version: Historical version requested by the operator.
        assay_id: Assay identifier used to restore ``_id`` after delta
            application.
        keep_version: Whether the selected version should remain visible in the
            projected document.

    Returns:
        A tuple of ``(assay_configuration, delta)`` where ``delta`` is the
        applied version delta or ``None`` when no historical projection was
        needed.
    """
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
    """Render and submit the create form for a DNA or RNA assay configuration.

    Args:
        category: Assay category, typically ``DNA`` or ``RNA``.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
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
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load {category} assay config create context",
            summary=f"Unable to load the {category} assay configuration form.",
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
            form_data["query"] = json.loads(request.form.get("query", "{}"))

        config = util.admin.process_form_to_config(form_data, context.schema)
        config.update(
            {
                "_id": f"{config['assay_name']}:{config['environment']}",
                "schema_name": context.schema["schema_id"],
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
        schema=context.schema,
        schemas=context.schemas,
        selected_schema=context.selected_schema,
        prefill_map_json=json.dumps(context.prefill_map),
    )


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
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("aspc"),
            headers=forward_headers(),
            params={"q": q, "page": page, "per_page": per_page},
        )
        assay_configs = payload.assay_configs
        pagination = payload.get("pagination", {})
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to fetch assay configs",
            summary="Unable to load assay configurations.",
        )
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
        form_data["query"] = util.common.safe_json_load(request.form.get("query", "{}"))

        updated_config = util.admin.process_form_to_config(form_data, context.schema)
        updated_config["_id"] = assay_config.get("_id")
        updated_config["updated_on"] = util.common.utc_now()
        updated_config["updated_by"] = current_user.email
        updated_config["schema_name"] = context.schema["schema_id"]
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
            flash_api_success("Assay configuration updated successfully.")
        except ApiRequestError as exc:
            flash_api_failure("Failed to update assay configuration.", exc)
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
        schema=context.schema,
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
        schema=context.schema,
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
