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

"""DNA translocation route handlers."""

from flask import Response, current_app as app, redirect, render_template, request, url_for
from flask_login import login_required
from coyote.blueprints.dna import dna_bp
from coyote.integrations.api.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>")
def show_transloc(sample_id: str, transloc_id: str) -> Response | str:
    """Show Translocation view page."""
    try:
        payload = get_web_api_client().get_json(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}",
            headers=build_forward_headers(request.headers),
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
        app.logger.error("DNA translocation detail API fetch failed for sample %s: %s", sample_id, exc)
        return Response(str(exc), status=exc.status_code or 502)


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/interestingtransloc", methods=["POST"])
@login_required
def mark_interesting_transloc(sample_id: str, transloc_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/interestingtransloc",
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to mark translocation interesting via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/uninterestingtransloc", methods=["POST"])
@login_required
def unmark_interesting_transloc(sample_id: str, transloc_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/uninterestingtransloc",
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to unmark translocation interesting via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/fptransloc", methods=["POST"])
@login_required
def mark_false_transloc(sample_id: str, transloc_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/fptransloc",
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to mark translocation false-positive via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/ptransloc", methods=["POST"])
@login_required
def unmark_false_transloc(sample_id: str, transloc_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/ptransloc",
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to unmark translocation false-positive via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/hide_variant_comment", methods=["POST"])
@login_required
def hide_transloc_comment(sample_id: str, transloc_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hide",
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to hide translocation comment via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/unhide_variant_comment", methods=["POST"])
@login_required
def unhide_transloc_comment(sample_id: str, transloc_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/unhide",
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to unhide translocation comment via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))
