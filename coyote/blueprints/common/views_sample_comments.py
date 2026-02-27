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

"""Common blueprint sample-comment routes."""

from flask import Response, current_app as app, flash, redirect, request, url_for
from flask_login import login_required

from coyote.blueprints.common import common_bp
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client
from coyote.integrations.api.web import log_api_error


def _redirect_for_omics_layer(sample_id: str, omics_layer: str) -> Response:
    if omics_layer == "dna":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    if omics_layer == "rna":
        return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))
    app.logger.info("Unrecognized omics type for sample %s! Unable to redirect to sample page", sample_id)
    flash("Unrecognized omics type! Unable to redirect to the sample page", "red")
    return redirect(url_for("home_bp.samples_home"))


@common_bp.route(
    "/dna/sample/<string:sample_id>/sample_comment",
    methods=["POST"],
    endpoint="add_dna_sample_comment",
)
@common_bp.route(
    "/rna/sample/<string:sample_id>/sample_comment",
    methods=["POST"],
    endpoint="add_rna_sample_comment",
)
@common_bp.route("/sample/<string:sample_id>/sample_comment", methods=["POST"])
@login_required
def add_sample_comment(sample_id: str) -> Response:
    """Add a sample comment."""
    data = request.form.to_dict()
    try:
        get_web_api_client().post_json(
            api_endpoints.sample(sample_id, "sample_comments", "add"),
            headers=forward_headers(),
            json_body={"form_data": data},
        )
        flash("Sample comment added", "green")
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to add sample comment via API for sample {sample_id}",
            flash_message="Failed to add sample comment",
        )
    if request.endpoint == "common_bp.add_dna_sample_comment":
        return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
    return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))


@common_bp.route("/sample/<string:sample_id>/hide_sample_comment", methods=["POST"])
@login_required
def hide_sample_comment(sample_id: str) -> Response:
    """
    Hides a sample comment for the given sample.

    Args:
        sample_id (str): The identifier of the sample.

    Returns:
        Response: Redirects to the appropriate variant or fusion list page based on sample type.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.sample(sample_id, "sample_comments", comment_id, "hide"),
            headers=forward_headers(),
        )
        omics_layer = str(payload.meta.get("omics_layer", "")).lower()
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to hide sample comment via API for sample {sample_id}",
            flash_message="Failed to hide sample comment",
        )
        return redirect(url_for("home_bp.samples_home"))
    return _redirect_for_omics_layer(sample_id, omics_layer)


@common_bp.route("/sample/unhide_sample_comment/<string:sample_id>", methods=["POST"])
@login_required
def unhide_sample_comment(sample_id: str) -> Response:
    """
    Unhides a previously hidden sample comment for the given sample.

    Args:
        sample_id (str): The identifier of the sample.

    Returns:
        Response: Redirects to the appropriate variant or fusion list page based on sample type.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        payload = get_web_api_client().post_json(
            api_endpoints.sample(sample_id, "sample_comments", comment_id, "unhide"),
            headers=forward_headers(),
        )
        omics_layer = str(payload.meta.get("omics_layer", "")).lower()
    except ApiRequestError as exc:
        log_api_error(
            exc,
            logger=app.logger,
            log_message=f"Failed to unhide sample comment via API for sample {sample_id}",
            flash_message="Failed to unhide sample comment",
        )
        return redirect(url_for("home_bp.samples_home"))
    return _redirect_for_omics_layer(sample_id, omics_layer)
