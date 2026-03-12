"""Admin sample-management routes."""

import json

from flask import Response, current_app as app, g, redirect, render_template, request, url_for
from flask_login import login_required

from coyote.blueprints.admin import admin_bp
from coyote.blueprints.home.forms import SampleSearchForm
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


@admin_bp.route("/manage-samples", methods=["GET", "POST"])
@login_required
def all_samples() -> str | Response:
    """Render the administrative sample-management page.

    Returns:
        The rendered management page response.
    """
    form = SampleSearchForm()
    search_str = ""

    if request.method == "POST" and form.validate_on_submit():
        search_str = form.sample_search.data

    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("samples"),
            headers=forward_headers(),
            params={"search": search_str} if search_str else None,
        )
        samples = payload.samples
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message="Failed to fetch admin sample list",
            summary="Unable to load samples.",
        )
    return render_template("samples/all_samples.html", all_samples=samples, form=form)


@admin_bp.route("/samples/<sample_id>/edit", methods=["GET", "POST"])
@login_required
def edit_sample(sample_id: str) -> str | Response:
    """Edit the raw stored representation of a sample.

    Args:
        sample_id: Sample identifier for the document being edited.

    Returns:
        The rendered form on ``GET`` or a redirect response after ``POST``.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.admin("samples", sample_id, "context"),
            headers=forward_headers(),
        )
        sample_doc = payload.sample
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load admin sample context for {sample_id}",
            summary="Unable to load the sample.",
            not_found_summary="Sample not found.",
        )
    sample_obj = sample_doc.pop("_id", sample_id)

    if request.method == "POST":
        json_blob = request.form.get("json_blob", "")
        try:
            updated_sample = json.loads(json_blob)
        except json.JSONDecodeError as exc:
            flash_api_failure("Invalid sample JSON.", ApiRequestError(str(exc)))
            return redirect(request.url)

        try:
            get_web_api_client().put_json(
                api_endpoints.admin("samples", sample_id),
                headers=forward_headers(),
                json_body={"sample": updated_sample},
            )
            flash_api_success("Sample updated successfully.")
            return redirect(url_for("admin_bp.all_samples"))
        except ApiRequestError as exc:
            flash_api_failure("Failed to update sample.", exc)

        g.audit_metadata = {"sample_id": str(sample_obj), "sample_name": sample_id}

    return render_template("samples/sample_edit.html", sample_blob=sample_doc)


@admin_bp.route("/manage-samples/<string:sample_id>/delete", methods=["GET"])
@login_required
def delete_sample(sample_id: str) -> Response:
    """Delete sample data across related collections.

    Args:
        sample_id: Sample identifier for the data being deleted.

    Returns:
        A redirect response back to the management page.
    """
    g.audit_metadata = {"sample": sample_id}
    try:
        payload = get_web_api_client().delete_json(
            api_endpoints.admin("samples", sample_id),
            headers=forward_headers(),
        )
        sample_name = payload.meta.get("sample_name", sample_id)
        for item in payload.meta.get("results", []):
            collection = item.get("collection", "unknown")
            if item.get("ok"):
                flash_api_success(f"Deleted {collection} for {sample_name}.")
            else:
                flash_api_failure(
                    f"Failed to delete {collection} for {sample_name}.",
                    ApiRequestError(item.get("error") or "Deletion failed."),
                )
    except ApiRequestError as exc:
        flash_api_failure("Failed to delete sample data.", exc)
    return redirect(url_for("admin_bp.all_samples"))
