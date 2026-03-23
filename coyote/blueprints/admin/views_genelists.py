"""Admin genelist-management routes."""

from __future__ import annotations

from copy import deepcopy

from flask import Response, abort, g, redirect, render_template, request, url_for
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
    flash_api_failure,
    flash_api_success,
    raise_page_load_error,
)


def _extract_genes_from_request(
    form_data: dict[str, list[str] | str], fallback_genes: list[str] | None = None
) -> list[str]:
    """Extract a normalized gene list from uploaded or pasted form input.

    Args:
        form_data: Submitted form payload.
        fallback_genes: Existing genes to reuse when no new input is supplied.

    Returns:
        A sorted, de-duplicated gene list.
    """
    fallback = fallback_genes or []
    if "genes_file" in request.files and request.files["genes_file"].filename:
        content = request.files["genes_file"].read().decode("utf-8")
        genes = [gene.strip() for gene in content.replace(",", "\n").splitlines() if gene.strip()]
    elif "genes_paste" in form_data and str(form_data["genes_paste"]).strip():
        pasted = str(form_data["genes_paste"]).replace(",", "\n")
        genes = [gene.strip() for gene in pasted.splitlines() if gene.strip()]
    else:
        genes = fallback
    genes = list(set(deepcopy(genes)))
    genes.sort()
    return genes


def _apply_selected_genelist_version(
    genelist: dict, selected_version: int | None, genelist_id: str | None = None
) -> tuple[dict, dict | None]:
    """Return the selected historical genelist version for diff-aware rendering.

    Args:
        genelist: Genelist document returned by the API context endpoint.
        selected_version: Historical version requested by the operator.
        genelist_id: Optional genelist identifier used to restore ``_id`` after
            delta application.

    Returns:
        A tuple of ``(genelist_document, delta)`` where ``delta`` is the
        applied version delta or ``None`` when no historical projection was
        needed.
    """
    delta = None
    if selected_version and selected_version != genelist.get("version"):
        version_index = next(
            (
                i
                for i, version_entry in enumerate(genelist.get("version_history", []))
                if version_entry["version"] == selected_version + 1
            ),
            None,
        )
        if version_index is not None:
            delta_blob = genelist["version_history"][version_index].get("delta", {})
            delta = delta_blob
            genelist = util.admin.apply_version_delta(deepcopy(genelist), delta_blob)
            if genelist_id:
                genelist["_id"] = genelist_id
    return genelist, delta


@admin_bp.route("/genelists", methods=["GET"])
@login_required
def manage_genelists() -> str:
    """Render the genelist management page.

    Returns:
        The rendered management page response.
    """
    q = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    per_page = max(1, min(request.args.get("per_page", default=30, type=int) or 30, 200))
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("genelists"),
            headers=forward_headers(),
            params={"q": q, "page": page, "per_page": per_page},
        )
        genelists = payload.genelists
        pagination = payload.get("pagination", {})
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to fetch genelists",
            summary="Unable to load genelists.",
        )
    return render_template(
        "isgl/manage_isgl.html",
        genelists=genelists,
        is_public=False,
        q=q,
        page=pagination.get("page", page),
        per_page=pagination.get("per_page", per_page),
        total=pagination.get("total", 0),
        has_next=pagination.get("has_next", False),
    )


@admin_bp.route("/genelists/new", methods=["GET", "POST"])
@login_required
def create_genelist() -> Response | str:
    """Create a managed genelist.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("genelists", "create_context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to load genelist create context",
            summary="Unable to load the genelist creation form.",
        )

    if request.method == "POST":
        form_data: dict[str, list[str] | str] = {
            key: (
                request.form.getlist(key)
                if len(request.form.getlist(key)) > 1
                else request.form[key]
            )
            for key in request.form
        }
        genes = _extract_genes_from_request(form_data)
        config = util.admin.process_form_to_config(form_data, context.schema)
        config["_id"] = config["name"]
        config["genes"] = genes
        config["gene_count"] = len(genes)
        try:
            get_web_api_client().post_json(
                api_endpoints.admin("genelists"),
                headers=forward_headers(),
                json_body={"config": config},
            )
            flash_api_success(f"Genelist {config['name']} created successfully.")
        except ApiRequestError as exc:
            flash_api_failure("Failed to create genelist.", exc)
        return redirect(url_for("admin_bp.manage_genelists"))

    return render_template(
        "isgl/create_isgl.html",
        schema=context.schema,
        assay_group_map=context.assay_group_map,
    )


@admin_bp.route("/genelists/<genelist_id>/edit", methods=["GET", "POST"])
@login_required
def edit_genelist(genelist_id: str) -> Response | str:
    """Edit a managed genelist.

    Args:
        genelist_id: Genelist identifier for the document being edited.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("genelists", genelist_id, "context"),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load genelist context for {genelist_id}",
            summary="Unable to load the genelist.",
            not_found_summary="Genelist not found.",
        )

    selected_version = request.args.get("version", type=int)
    genelist, delta = _apply_selected_genelist_version(
        context.genelist, selected_version, genelist_id
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
        updated = util.admin.process_form_to_config(form_data, context.schema)
        genes = _extract_genes_from_request(form_data, genelist.get("genes", []))
        updated["genes"] = genes
        updated["gene_count"] = len(genes)
        try:
            get_web_api_client().put_json(
                api_endpoints.admin("genelists", genelist_id),
                headers=forward_headers(),
                json_body={"config": updated},
            )
            g.audit_metadata = {"genelist": genelist_id}
            flash_api_success(f"Genelist '{genelist_id}' updated successfully.")
        except ApiRequestError as exc:
            flash_api_failure("Failed to update genelist.", exc)
        return redirect(url_for("admin_bp.manage_genelists"))

    return render_template(
        "isgl/edit_isgl.html",
        isgl=genelist,
        schema=context.schema,
        assay_group_map=context.assay_group_map,
        selected_version=selected_version,
        delta=delta,
    )


@admin_bp.route("/genelists/<genelist_id>/view", methods=["GET"])
@login_required
def view_genelist(genelist_id: str) -> Response | str:
    """Display a read-only genelist view.

    Args:
        genelist_id: Genelist identifier for the document being displayed.

    Returns:
        The rendered detail page response.
    """
    selected_assay = request.args.get("assay")
    try:
        view_context = get_web_api_client().get_json(
            api_endpoints.admin("genelists", genelist_id, "view_context"),
            headers=forward_headers(),
            params={"assay": selected_assay} if selected_assay else None,
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load genelist view context for {genelist_id}",
            summary="Unable to load the genelist.",
            not_found_summary="Genelist not found.",
        )

    selected_version = request.args.get("version", type=int)
    genelist, delta = _apply_selected_genelist_version(view_context.genelist, selected_version)

    return render_template(
        "isgl/view_isgl.html",
        genelist=genelist,
        selected_assay=selected_assay,
        filtered_genes=view_context.filtered_genes,
        is_public=False,
        selected_version=selected_version or genelist.get("version"),
        panel_germline_genes=view_context.panel_germline_genes,
        delta=delta,
    )


@admin_bp.route("/genelists/<genelist_id>/toggle", methods=["GET"])
@login_required
def toggle_genelist(genelist_id: str) -> Response:
    """Toggle the active flag on a genelist.

    Args:
        genelist_id: Genelist identifier for the document being updated.

    Returns:
        A redirect response back to the management page.
    """
    try:
        payload = get_web_api_client().patch_json(
            api_endpoints.admin("genelists", genelist_id, "status"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", True))
        g.audit_metadata = {
            "genelist": genelist_id,
            "genelist_status": "Active" if new_status else "Inactive",
        }
        flash_api_success(
            f"Genelist '{genelist_id}' is now {'active' if new_status else 'inactive'}."
        )
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash_api_failure("Failed to update genelist status.", exc)
    return redirect(url_for("admin_bp.manage_genelists"))


@admin_bp.route("/genelists/<genelist_id>/delete", methods=["GET"])
@login_required
def delete_genelist(genelist_id: str) -> Response:
    """Delete a genelist.

    Args:
        genelist_id: Genelist identifier for the document being deleted.

    Returns:
        A redirect response back to the management page.
    """
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("genelists", genelist_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"genelist": genelist_id}
        flash_api_success(f"Genelist '{genelist_id}' deleted successfully.")
    except ApiRequestError as exc:
        flash_api_failure("Failed to delete genelist.", exc)
    return redirect(url_for("admin_bp.manage_genelists"))
