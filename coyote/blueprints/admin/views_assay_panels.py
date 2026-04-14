"""Admin assay-panel routes."""

from __future__ import annotations

from flask import Response, abort, flash, g, jsonify, redirect, render_template, request, url_for
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


def _load_panel_context(assay_panel_id: str):
    """Load assay-panel context for edit, view, and print screens.

    Args:
        assay_panel_id: Assay-panel identifier.

    Returns:
        The decoded API context payload for the assay panel.
    """
    with api_page_guard(
        logger=app.logger,
        log_message=f"Failed to load assay panel context for {assay_panel_id}",
        summary="Unable to load the assay panel.",
        not_found_summary="Assay panel not found.",
    ):
        return get_web_api_client().get_json(
            api_endpoints.admin("asp", assay_panel_id, "context"),
            headers=forward_headers(),
        )


def _apply_selected_panel_version(
    panel: dict, selected_version: int | None, panel_id: str, keep_version: bool = False
) -> tuple[dict, dict | None]:
    """Return the selected historical panel version for diff-aware rendering."""
    from coyote.util.admin_utility import apply_selected_version

    return apply_selected_version(
        panel, selected_version, id_field="_id", id_value=panel_id, keep_version=keep_version
    )


@admin_bp.route("/asp/manage", methods=["GET"])
@login_required
def manage_assay_panels():
    """Render the assay-panel management page.

    Returns:
        The rendered management page response.
    """
    q = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    per_page = max(1, min(request.args.get("per_page", default=30, type=int) or 30, 200))
    with api_page_guard(
        logger=app.logger,
        log_message="Failed to fetch assay panels",
        summary="Unable to load assay panels.",
    ):
        payload = get_web_api_client().get_json(
            api_endpoints.admin("asp"),
            headers=forward_headers(),
            params={"q": q, "page": page, "per_page": per_page},
        )
        panels = payload.panels
        pagination = payload.get("pagination", {})
    return render_template(
        "asp/manage_asp.html",
        panels=panels,
        q=q,
        page=pagination.get("page", page),
        per_page=pagination.get("per_page", per_page),
        total=pagination.get("total", 0),
        has_next=pagination.get("has_next", False),
    )


@admin_bp.route("/asp/new", methods=["GET", "POST"])
@login_required
def create_assay_panel():
    """Create an assay panel definition.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    with api_page_guard(
        logger=app.logger,
        log_message="Failed to load assay panel create context",
        summary="Unable to load the assay panel creation form.",
    ):
        context = get_web_api_client().get_json(
            api_endpoints.admin("asp", "create_context"),
            headers=forward_headers(),
        )

    if request.method == "POST":
        try:
            form_data: dict[str, list[str] | str] = {
                key: (
                    request.form.getlist(key)
                    if len(request.form.getlist(key)) > 1
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
            config = util.admin.process_form_to_config(form_data, context.form)
            assay_name = str(config.get("assay_name") or "").strip()
            if not assay_name:
                raise ValueError("Assay name is required.")
            config["_id"] = assay_name
            config["covered_genes"] = covered_genes
            config["germline_genes"] = germline_genes
            get_web_api_client().post_json(
                api_endpoints.admin("asp"),
                headers=forward_headers(),
                json_body={"config": config},
            )
            g.audit_metadata = {"panel": config["_id"]}
            flash_api_success(f"Panel {config['assay_name']} created successfully.")
        except ApiRequestError as exc:
            flash_api_failure("Failed to create assay panel.", exc)
        except Exception as exc:
            app.logger.exception("Failed to build assay panel create payload: %s", exc)
            flash(f"Failed to create assay panel. {exc}", "red")
        return redirect(url_for("admin_bp.manage_assay_panels"))

    return render_template(
        "asp/create_asp.html",
        schema=context.form,
    )


@admin_bp.route("/asp/validate_asp_id", methods=["POST"])
@login_required
def validate_asp_id() -> Response:
    """Validate whether an asp_id already exists."""
    asp_id = str((request.json or {}).get("asp_id", "")).strip()
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.admin("asp", "validate_asp_id"),
            headers=forward_headers(),
            json_body={"asp_id": asp_id},
        )
        return jsonify({"exists": bool(payload.get("exists", False))})
    except ApiRequestError as exc:
        return jsonify({"exists": False, "error": str(exc)}), 502


@admin_bp.route("/asp/<assay_panel_id>/edit", methods=["GET", "POST"])
@login_required
def edit_assay_panel(assay_panel_id: str) -> str | Response:
    """Edit an assay panel definition.

    Args:
        assay_panel_id: Assay-panel identifier for the document being edited.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    context = _load_panel_context(assay_panel_id)

    selected_version = request.args.get("version", type=int)
    panel, delta = _apply_selected_panel_version(context.panel, selected_version, assay_panel_id)

    if request.method == "POST":
        form_data: dict[str, list[str] | str] = {
            key: (
                request.form.getlist(key)
                if len(request.form.getlist(key)) > 1
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

        updated = util.admin.process_form_to_config(form_data, context.form)
        updated["_id"] = panel["_id"]
        updated["covered_genes"] = covered_genes
        updated["germline_genes"] = germline_genes
        try:
            get_web_api_client().put_json(
                api_endpoints.admin("asp", assay_panel_id),
                headers=forward_headers(),
                json_body={"config": updated},
            )
            g.audit_metadata = {"panel": assay_panel_id}
            flash_api_success(f"Panel '{panel['assay_name']}' updated successfully.")
        except ApiRequestError as exc:
            flash_api_failure("Failed to update assay panel.", exc)
        return redirect(url_for("admin_bp.manage_assay_panels"))

    return render_template(
        "asp/edit_asp.html",
        schema=context.form,
        panel=panel,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/asp/<assay_panel_id>/view", methods=["GET"])
@login_required
def view_assay_panel(assay_panel_id: str) -> Response | str:
    """Display a read-only assay panel view.

    Args:
        assay_panel_id: Assay-panel identifier for the document being displayed.

    Returns:
        The rendered detail page response.
    """
    context = _load_panel_context(assay_panel_id)

    selected_version = request.args.get("version", type=int)
    panel, delta = _apply_selected_panel_version(context.panel, selected_version, assay_panel_id)

    return render_template(
        "asp/view_asp.html",
        panel=panel,
        schema=context.form,
        selected_version=selected_version or panel.get("version"),
        delta=delta,
    )


@admin_bp.route("/asp/<panel_id>/print", methods=["GET"])
@login_required
def print_assay_panel(panel_id: str) -> str | Response:
    """Render a print-friendly assay panel document.

    Args:
        panel_id: Assay-panel identifier for the document being printed.

    Returns:
        The rendered print view response.
    """
    context = _load_panel_context(panel_id)

    selected_version = request.args.get("version", type=int)
    panel, _ = _apply_selected_panel_version(
        context.panel, selected_version, panel_id, keep_version=True
    )

    return render_template(
        "asp/print_asp.html",
        schema=context.form,
        config=panel,
        now=util.common.utc_now(),
        selected_version=selected_version,
    )


@admin_bp.route("/asp/<assay_panel_id>/toggle", methods=["POST", "GET"])
@login_required
def toggle_assay_panel_active(assay_panel_id: str) -> Response:
    """Toggle the active flag on an assay panel.

    Args:
        assay_panel_id: Assay-panel identifier for the document being updated.

    Returns:
        A redirect response back to the management page.
    """
    try:
        payload = get_web_api_client().patch_json(
            api_endpoints.admin("asp", assay_panel_id, "status"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", True))
        g.audit_metadata = {
            "panel": assay_panel_id,
            "panel_status": "Active" if new_status else "Inactive",
        }
        flash_api_success(
            f"Panel '{assay_panel_id}' is now {'Active' if new_status else 'Inactive'}."
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash_api_failure("Failed to update assay panel status.", exc)
    return redirect(url_for("admin_bp.manage_assay_panels"))


@admin_bp.route("/asp/<assay_panel_id>/delete", methods=["GET"])
@login_required
def delete_assay_panel(assay_panel_id: str) -> Response:
    """Delete an assay panel definition.

    Args:
        assay_panel_id: Assay-panel identifier for the document being deleted.

    Returns:
        A redirect response back to the management page.
    """
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("asp", assay_panel_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"panel": assay_panel_id}
        flash_api_success(f"Panel '{assay_panel_id}' deleted successfully.")
    except ApiRequestError as exc:
        flash_api_failure("Failed to delete assay panel.", exc)
    return redirect(url_for("admin_bp.manage_assay_panels"))
