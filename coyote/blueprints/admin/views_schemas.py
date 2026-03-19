"""Admin schema-management routes."""

import json

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


@admin_bp.route("/schemas")
@login_required
def schemas() -> str:
    """Render the schema-management page.

    Returns:
        The rendered management page response.
    """
    q = (request.args.get("q") or "").strip()
    page = max(1, request.args.get("page", default=1, type=int) or 1)
    per_page = max(1, min(request.args.get("per_page", default=30, type=int) or 30, 200))
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("schemas"),
            headers=forward_headers(),
            params={"q": q, "page": page, "per_page": per_page},
        )
        schemas = payload.schemas
        pagination = payload.get("pagination", {})
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to fetch schemas",
            summary="Unable to load schemas.",
        )
    return render_template(
        "schemas/schemas.html",
        schemas=schemas,
        q=q,
        page=pagination.get("page", page),
        per_page=pagination.get("per_page", per_page),
        total=pagination.get("total", 0),
        has_next=pagination.get("has_next", False),
    )


@admin_bp.route("/schemas/<schema_id>/toggle", methods=["POST", "GET"])
@login_required
def toggle_schema_active(schema_id: str) -> Response:
    """Toggle the active flag on a schema.

    Args:
        schema_id: Schema identifier for the document being updated.

    Returns:
        A redirect response back to the management page.
    """
    try:
        payload = get_web_api_client().patch_json(
            api_endpoints.admin("schemas", schema_id, "status"),
            headers=forward_headers(),
        )
        new_status = bool(payload.meta.get("is_active", True))
        g.audit_metadata = {
            "schema": schema_id,
            "schema_status": "Active" if new_status else "Inactive",
        }
        flash_api_success(f"Schema '{schema_id}' is now {'active' if new_status else 'inactive'}.")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash_api_failure("Failed to update schema status.", exc)
    return redirect(url_for("admin_bp.schemas"))


@admin_bp.route("/schemas/<schema_id>/edit", methods=["GET", "POST"])
@login_required
def edit_schema(schema_id: str) -> str | Response:
    """Edit a schema document.

    Args:
        schema_id: Schema identifier for the document being edited.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    try:
        context = get_web_api_client().get_json(
            api_endpoints.admin("schemas", schema_id, "context"),
            headers=forward_headers(),
        )
        schema_doc = context.schema
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load schema context for {schema_id}",
            summary="Unable to load the schema.",
            not_found_summary="Schema not found.",
        )

    if request.method == "POST":
        json_blob = request.form.get("json_blob", "")
        try:
            updated_schema = json.loads(json_blob)
            errors = util.admin.validate_schema_structure(updated_schema)
            if errors:
                for err in errors:
                    flash_api_failure(str(err), ApiRequestError(str(err)))
                return render_template("schemas/schema_edit.html", schema_blob=updated_schema)
        except json.JSONDecodeError as exc:
            flash_api_failure("Invalid schema JSON.", ApiRequestError(str(exc)))
            return redirect(request.url)

        try:
            get_web_api_client().put_json(
                api_endpoints.admin("schemas", schema_id),
                headers=forward_headers(),
                json_body={"schema": updated_schema},
            )
            flash_api_success("Schema updated successfully.")
            return redirect(url_for("admin_bp.schemas"))
        except ApiRequestError as exc:
            flash_api_failure("Failed to update schema.", exc)

        g.audit_metadata = {"schema": schema_id}

    return render_template("schemas/schema_edit.html", schema_blob=schema_doc)


@admin_bp.route("/schemas/new", methods=["GET", "POST"])
@login_required
def create_schema() -> str | Response:
    """Create a schema document.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    if request.method == "POST":
        json_blob = request.form.get("json_blob")
        try:
            parsed_schema = json.loads(json_blob)

            errors = util.admin.validate_schema_structure(parsed_schema)
            if errors:
                for err in errors:
                    flash_api_failure(str(err), ApiRequestError(str(err)))
                return render_template("schemas/schema_create.html", initial_blob=parsed_schema)

            get_web_api_client().post_json(
                api_endpoints.admin("schemas"),
                headers=forward_headers(),
                json_body={"schema": parsed_schema},
            )
            flash_api_success("Schema created successfully.")
            return redirect(url_for("admin_bp.schemas"))

        except ApiRequestError as exc:
            flash_api_failure("Failed to create schema.", exc)

        g.audit_metadata = {"schema": parsed_schema.get("schema_name")}

    initial_blob = util.admin.load_json5_template()
    return render_template("schemas/schema_create.html", initial_blob=initial_blob)


@admin_bp.route("/schemas/<schema_id>/delete", methods=["GET"])
@login_required
def delete_schema(schema_id: str) -> Response:
    """Delete a schema document.

    Args:
        schema_id: Schema identifier for the document being deleted.

    Returns:
        A redirect response back to the management page.
    """
    try:
        get_web_api_client().delete_json(
            api_endpoints.admin("schemas", schema_id),
            headers=forward_headers(),
        )
        g.audit_metadata = {"schema": schema_id}
        flash_api_success(f"Schema '{schema_id}' deleted successfully.")
    except ApiRequestError as exc:
        if exc.status_code == 404:
            return abort(404)
        flash_api_failure("Failed to delete schema.", exc)
    return redirect(url_for("admin_bp.schemas"))
