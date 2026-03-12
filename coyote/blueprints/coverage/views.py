
"""Coverage review routes for low-coverage inspection and blacklist actions."""


from flask import (
    current_app as app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_required
from coyote.blueprints.coverage import cov_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.services.api_client.web import flash_api_failure, raise_page_load_error


@cov_bp.route("/<string:sample_id>", methods=["GET", "POST"])
def get_cov(sample_id):
    """Render the coverage review page for a sample."""
    cov_cutoff = 500
    if request.method == "POST":
        cov_cutoff_form = request.form.get("depth_cutoff")
        cov_cutoff = int(cov_cutoff_form)
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.coverage("samples", sample_id),
            headers=forward_headers(),
            params={"cov_cutoff": cov_cutoff},
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load coverage via API for sample {sample_id}",
            summary="Unable to load coverage data for this sample.",
            not_found_summary="Coverage data for this sample was not found.",
        )

    return render_template(
        "show_cov.html",
        coverage=payload.coverage,
        cov_cutoff=payload.cov_cutoff,
        sample=payload.sample,
        genelists=payload.genelists,
        smp_grp=payload.smp_grp,
        cov_table=payload.cov_table,
    )


@app.route("/update-gene-status", methods=["POST"])
@login_required
def update_gene_status():
    """Apply a blacklist mutation for a coverage gene row via AJAX."""
    data = request.get_json()
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.coverage("blacklist", "entries"),
            headers=forward_headers(),
            json_body=data,
        )
        return jsonify(payload)
    except ApiRequestError as exc:
        app.logger.warning("Coverage blacklist update failed: %s", exc)
        return jsonify({"message": str(exc)}), exc.status_code or 502


@cov_bp.route("/blacklisted/<string:group>", methods=["GET", "POST"])
def show_blacklisted_regions(group):
    """Render the blacklist overview for an assay or sample group."""
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.coverage("blacklisted", group),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        raise_page_load_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to load blacklisted regions via API for group {group}",
            summary="Unable to load the blacklist overview.",
            not_found_summary="The requested blacklist group was not found.",
        )

    return render_template("show_blacklisted.html", blacklisted=payload.blacklisted, group=payload.group)


@cov_bp.route("/remove_blacklist/<string:obj_id>/<string:group>", methods=["GET"])
def remove_blacklist(obj_id, group):
    """Remove a blacklist entry and return to the blacklist overview."""
    try:
        get_web_api_client().delete_json(
            api_endpoints.coverage("blacklist", "entries", obj_id),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.warning("Failed to remove blacklist entry %s for group %s: %s", obj_id, group, exc)
        flash_api_failure("Unable to remove the blacklist entry.", exc)
    return redirect(url_for("cov_bp.show_blacklisted_regions", group=group))
