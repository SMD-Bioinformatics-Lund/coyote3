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
from coyote.blueprints.dna import dna_bp
from coyote.extensions import store, util
from coyote.util.decorators.access import require_sample_access
from coyote.util.misc import get_sample_and_assay_config
from coyote.services.auth.decorators import require
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>")
@require_sample_access("sample_id")
def show_transloc(sample_id: str, transloc_id: str) -> Response | str:
    """Show Translocation view page."""
    use_api_translocs = bool(app.config.get("WEB_API_READ_DNA_VARIANTS", False)) and request.method == "GET"
    if use_api_translocs:
        try:
            payload = get_web_api_client().get_dna_translocation(
                sample_id=sample_id,
                transloc_id=transloc_id,
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
            app.logger.warning("DNA translocation detail API fetch failed for sample %s: %s", sample_id, exc)
            if app.config.get("WEB_API_STRICT_MODE", False):
                return Response(str(exc), status=exc.status_code or 502)

    transloc = store.transloc_handler.get_transloc(transloc_id)

    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    assay_group: str = assay_config.get("asp_group", "unknown")

    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    if not sample_ids:
        sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)
    hidden_transloc_comments = store.transloc_handler.hidden_transloc_comments(transloc_id)

    vep_conseq_meta = store.vep_meta_handler.get_conseq_translations(sample.get("vep", 103))

    annotations = store.transloc_handler.get_transloc_annotations(transloc)
    app.logger.info("Loaded DNA translocation detail from Mongo for sample %s", sample_id)
    return render_template(
        "show_transloc.html",
        tl=transloc,
        sample=sample,
        assay_group=assay_group,
        classification=999,
        annotations=annotations,
        bam_id=bam_id,
        vep_conseq_translations=vep_conseq_meta,
        hidden_comments=hidden_transloc_comments,
    )


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/interestingtransloc", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def mark_interesting_transloc(sample_id: str, transloc_id: str) -> Response:
    store.transloc_handler.mark_interesting_transloc(transloc_id)
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/uninterestingtransloc", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def unmark_interesting_transloc(sample_id: str, transloc_id: str) -> Response:
    store.transloc_handler.unmark_interesting_transloc(transloc_id)
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/fptransloc", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def mark_false_transloc(sample_id: str, transloc_id: str) -> Response:
    store.transloc_handler.mark_false_positive_transloc(transloc_id)
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/ptransloc", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def unmark_false_transloc(sample_id: str, transloc_id: str) -> Response:
    store.transloc_handler.unmark_false_positive_transloc(transloc_id)
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/hide_variant_comment", methods=["POST"])
@require("hide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def hide_transloc_comment(sample_id: str, transloc_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.transloc_handler.hide_transloc_comment(transloc_id, comment_id)
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))


@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>/unhide_variant_comment", methods=["POST"])
@require("unhide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def unhide_transloc_comment(sample_id: str, transloc_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.transloc_handler.unhide_transloc_comment(transloc_id, comment_id)
    return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=transloc_id))
