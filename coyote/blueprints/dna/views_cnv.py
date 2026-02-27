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

"""DNA CNV route handlers."""

from flask import Response, current_app as app, redirect, render_template, request, url_for
from flask_login import login_required
from coyote.blueprints.dna import dna_bp
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


@dna_bp.route("/<string:sample_id>/cnv/<string:cnv_id>")
def show_cnv(sample_id: str, cnv_id: str) -> Response | str:
    """
    Show CNVs view page.
    """
    try:
        payload = get_web_api_client().get_json(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}",
            headers=forward_headers(),
        )
        app.logger.info("Loaded DNA CNV detail from API service for sample %s", sample_id)
        return render_template(
            "show_cnvwgs.html",
            cnv=payload.cnv,
            sample=payload.sample,
            assay_group=payload.assay_group,
            classification=999,
            annotations=payload.annotations,
            sample_ids=payload.sample_ids,
            bam_id=payload.bam_id,
            hidden_comments=payload.hidden_comments,
        )
    except ApiRequestError as exc:
        app.logger.error("DNA CNV detail API fetch failed for sample %s: %s", sample_id, exc)
        return Response(str(exc), status=exc.status_code or 502)


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/unmarkinterestingcnv", methods=["POST"])
@login_required
def unmark_interesting_cnv(sample_id: str, cnv_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unmarkinteresting",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to unmark CNV interesting via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/interestingcnv", methods=["POST"])
@login_required
def mark_interesting_cnv(sample_id: str, cnv_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/interesting",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to mark CNV interesting via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/fpcnv", methods=["POST"])
@login_required
def mark_false_cnv(sample_id: str, cnv_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/fpcnv",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to mark CNV false-positive via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("/<string:sample_id>/cnv/<string:cnv_id>/unfpcnv", methods=["POST"])
@login_required
def unmark_false_cnv(sample_id: str, cnv_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unfpcnv",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to unmark CNV false-positive via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/noteworthycnv", methods=["POST"])
@login_required
def mark_noteworthy_cnv(sample_id: str, cnv_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/noteworthycnv",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to mark CNV noteworthy via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/notnoteworthycnv", methods=["POST"])
@login_required
def unmark_noteworthy_cnv(sample_id: str, cnv_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/notnoteworthycnv",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to unmark CNV noteworthy via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/hide_cnv_comment", methods=["POST"])
@login_required
def hide_cnv_comment(sample_id: str, cnv_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hide",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to hide CNV comment via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/unhide_cnv_comment", methods=["POST"])
@login_required
def unhide_cnv_comment(sample_id: str, cnv_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/unhide",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to unhide CNV comment via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))
