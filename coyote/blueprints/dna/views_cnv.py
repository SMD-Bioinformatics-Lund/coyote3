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
from coyote.blueprints.dna import dna_bp
from coyote.extensions import store
from coyote.util.decorators.access import require_sample_access
from coyote.services.auth.decorators import require
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@dna_bp.route("/<string:sample_id>/cnv/<string:cnv_id>")
@require_sample_access("sample_id")
def show_cnv(sample_id: str, cnv_id: str) -> Response | str:
    """
    Show CNVs view page.
    """
    try:
        payload = get_web_api_client().get_dna_cnv(
            sample_id=sample_id,
            cnv_id=cnv_id,
            headers=build_forward_headers(request.headers),
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
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def unmark_interesting_cnv(sample_id: str, cnv_id: str) -> Response:
    store.cnv_handler.unmark_interesting_cnv(cnv_id)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/interestingcnv", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def mark_interesting_cnv(sample_id: str, cnv_id: str) -> Response:
    store.cnv_handler.mark_interesting_cnv(cnv_id)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/fpcnv", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def mark_false_cnv(sample_id: str, cnv_id: str) -> Response:
    store.cnv_handler.mark_false_positive_cnv(cnv_id)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("/<string:sample_id>/cnv/<string:cnv_id>/unfpcnv", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def unmark_false_cnv(sample_id: str, cnv_id: str) -> Response:
    store.cnv_handler.unmark_false_positive_cnv(cnv_id)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/noteworthycnv", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def mark_noteworthy_cnv(sample_id: str, cnv_id: str) -> Response:
    store.cnv_handler.noteworthy_cnv(cnv_id)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/notnoteworthycnv", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def unmark_noteworthy_cnv(sample_id: str, cnv_id: str) -> Response:
    store.cnv_handler.unnoteworthy_cnv(cnv_id)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/hide_cnv_comment", methods=["POST"])
@require("hide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def hide_cnv_comment(sample_id: str, cnv_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.cnv_handler.hide_cnvs_comment(cnv_id, comment_id)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/unhide_cnv_comment", methods=["POST"])
@require("unhide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def unhide_cnv_comment(sample_id: str, cnv_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.cnv_handler.unhide_cnvs_comment(cnv_id, comment_id)
    return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id))
