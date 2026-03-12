"""DNA translocation route handlers."""

from flask import Response, redirect, render_template, request, url_for
from flask import current_app as app
from flask_login import login_required

from coyote.blueprints.dna import dna_bp
from coyote.services.api_client import endpoints as api_endpoints
from coyote.services.api_client.api_client import (
    ApiRequestError,
    forward_headers,
    get_web_api_client,
)


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>")
def show_transloc(sample_id: str, transloc_id: str) -> Response | str:
    """Show Translocation view page."""
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.dna_sample(sample_id, "translocations", transloc_id),
            headers=forward_headers(),
        )
        app.logger.info("Loaded DNA translocation detail from API service for sample %s", sample_id)
        return render_template(
            "show_transloc.html",
            tl=payload.translocation,
            sample=payload.sample,
            assay_group=payload.assay_group,
            classification=999,
            annotations=payload.annotations,
            bam_id=payload.bam_id,
            vep_conseq_translations=payload.vep_conseq_translations,
            hidden_comments=payload.hidden_comments,
        )
    except ApiRequestError as exc:
        app.logger.error(
            "DNA translocation detail API fetch failed for sample %s: %s", sample_id, exc
        )
        return Response(str(exc), status=exc.status_code or 502)


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/interestingtransloc", methods=["POST"]
)
@login_required
def mark_interesting_transloc(sample_id: str, transloc_id: str) -> Response:
    """Handle mark interesting transloc.

    Args:
        sample_id (str): Value for ``sample_id``.
        transloc_id (str): Value for ``transloc_id``.

    Returns:
        Response: The function result.
    """
    try:
        get_web_api_client().patch_json(
            api_endpoints.dna_sample(
                sample_id, "translocations", transloc_id, "flags", "interesting"
            ),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to mark translocation interesting via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/uninterestingtransloc", methods=["POST"]
)
@login_required
def unmark_interesting_transloc(sample_id: str, transloc_id: str) -> Response:
    """Handle unmark interesting transloc.

    Args:
        sample_id (str): Value for ``sample_id``.
        transloc_id (str): Value for ``transloc_id``.

    Returns:
        Response: The function result.
    """
    try:
        get_web_api_client().delete_json(
            api_endpoints.dna_sample(
                sample_id, "translocations", transloc_id, "flags", "interesting"
            ),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to unmark translocation interesting via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/fptransloc", methods=["POST"])
@login_required
def mark_false_transloc(sample_id: str, transloc_id: str) -> Response:
    """Handle mark false transloc.

    Args:
        sample_id (str): Value for ``sample_id``.
        transloc_id (str): Value for ``transloc_id``.

    Returns:
        Response: The function result.
    """
    try:
        get_web_api_client().patch_json(
            api_endpoints.dna_sample(
                sample_id, "translocations", transloc_id, "flags", "false-positive"
            ),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to mark translocation false-positive via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/ptransloc", methods=["POST"])
@login_required
def unmark_false_transloc(sample_id: str, transloc_id: str) -> Response:
    """Handle unmark false transloc.

    Args:
        sample_id (str): Value for ``sample_id``.
        transloc_id (str): Value for ``transloc_id``.

    Returns:
        Response: The function result.
    """
    try:
        get_web_api_client().delete_json(
            api_endpoints.dna_sample(
                sample_id, "translocations", transloc_id, "flags", "false-positive"
            ),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to unmark translocation false-positive via API for sample %s: %s",
            sample_id,
            exc,
        )
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/hide_variant_comment", methods=["POST"]
)
@login_required
def hide_transloc_comment(sample_id: str, transloc_id: str) -> Response:
    """Handle hide transloc comment.

    Args:
        sample_id (str): Value for ``sample_id``.
        transloc_id (str): Value for ``transloc_id``.

    Returns:
        Response: The function result.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().patch_json(
            api_endpoints.dna_sample(
                sample_id, "translocations", transloc_id, "comments", comment_id, "hidden"
            ),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to hide translocation comment via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/unhide_variant_comment", methods=["POST"]
)
@login_required
def unhide_transloc_comment(sample_id: str, transloc_id: str) -> Response:
    """Handle unhide transloc comment.

    Args:
        sample_id (str): Value for ``sample_id``.
        transloc_id (str): Value for ``transloc_id``.

    Returns:
        Response: The function result.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().delete_json(
            api_endpoints.dna_sample(
                sample_id, "translocations", transloc_id, "comments", comment_id, "hidden"
            ),
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to unhide translocation comment via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))
