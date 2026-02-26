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

"""DNA variant action/comment route handlers."""

from flask import current_app as app
from flask import Response, flash, redirect, request, url_for
from coyote.blueprints.dna import dna_bp
from coyote.extensions import store
from coyote.util.decorators.access import require_sample_access
from coyote.services.auth.decorators import require
from coyote.services.dna.dna_variants import get_variant_nomenclature
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/unfp", methods=["POST"])
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def unmark_false_variant(sample_id: str, var_id: str) -> Response:
    try:
        get_web_api_client().unmark_dna_variant_false_positive(
            sample_id=sample_id,
            var_id=var_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to unmark variant false-positive via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/fp", methods=["POST"])
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def mark_false_variant(sample_id: str, var_id: str) -> Response:
    try:
        get_web_api_client().mark_dna_variant_false_positive(
            sample_id=sample_id,
            var_id=var_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to mark variant false-positive via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/uninterest", methods=["POST"])
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def unmark_interesting_variant(sample_id: str, var_id: str) -> Response:
    try:
        get_web_api_client().unmark_dna_variant_interesting(
            sample_id=sample_id,
            var_id=var_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to unmark variant interesting via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/interest", methods=["POST"])
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def mark_interesting_variant(sample_id: str, var_id: str) -> Response:
    try:
        get_web_api_client().mark_dna_variant_interesting(
            sample_id=sample_id,
            var_id=var_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to mark variant interesting via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/relevant", methods=["POST"])
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def unmark_irrelevant_variant(sample_id: str, var_id: str) -> Response:
    try:
        get_web_api_client().unmark_dna_variant_irrelevant(
            sample_id=sample_id,
            var_id=var_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to unmark variant irrelevant via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/irrelevant", methods=["POST"])
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def mark_irrelevant_variant(sample_id: str, var_id: str) -> Response:
    try:
        get_web_api_client().mark_dna_variant_irrelevant(
            sample_id=sample_id,
            var_id=var_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to mark variant irrelevant via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/blacklist", methods=["POST"])
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def add_variant_to_blacklist(sample_id: str, var_id: str) -> Response:
    try:
        get_web_api_client().blacklist_dna_variant(
            sample_id=sample_id,
            var_id=var_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to blacklist variant via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/classify", methods=["POST"], endpoint="classify_variant")
@dna_bp.route("/<string:sample_id>/fus/<string:fus_id>/classify", methods=["POST"], endpoint="classify_fusion")
@require(permission="assign_tier", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def classify_variant(sample_id: str, id: str = None) -> Response:
    id = id or request.view_args.get("var_id") or request.view_args.get("fus_id")
    form_data = request.form.to_dict()
    nomenclature, _variant = get_variant_nomenclature(form_data)
    try:
        get_web_api_client().classify_dna_variant(
            sample_id=sample_id,
            target_id=id,
            form_data=form_data,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to classify variant via API for sample %s: %s", sample_id, exc)

    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=id))
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=id))


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/rmclassify",
    methods=["POST"],
    endpoint="remove_classified_variant",
)
@dna_bp.route(
    "/<string:sample_id>/fus/<string:fus_id>/rmclassify",
    methods=["POST"],
    endpoint="remove_classified_fusion",
)
@require(permission="remove_tier", min_role="admin")
@require_sample_access("sample_id")
def remove_classified_variant(sample_id: str, id: str | None = None) -> Response:
    id = id or request.view_args.get("var_id") or request.view_args.get("fus_id")
    form_data = request.form.to_dict()
    nomenclature, _variant = get_variant_nomenclature(form_data)

    try:
        get_web_api_client().remove_dna_variant_classification(
            sample_id=sample_id,
            target_id=id,
            form_data=form_data,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to remove classification via API for sample %s: %s", sample_id, exc)
    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=id))
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=id))


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/add_variant_comment",
    methods=["POST"],
    endpoint="add_variant_comment",
)
@dna_bp.route(
    "/<string:sample_id>/cnv/<string:cnv_id>/add_cnv_comment",
    methods=["POST"],
    endpoint="add_cnv_comment",
)
@dna_bp.route(
    "/<string:sample_id>/fusion/<string:fus_id>/add_fusion_comment",
    methods=["POST"],
    endpoint="add_fusion_comment",
)
@dna_bp.route(
    "/<string:sample_id>/translocation/<string:transloc_id>/add_translocation_comment",
    methods=["POST"],
    endpoint="add_translocation_comment",
)
@require("add_variant_comment", min_role="user", min_level=9)
@require_sample_access("sample_id")
def add_var_comment(sample_id: str, id: str = None, **kwargs) -> Response | str:
    id = (
        id
        or request.view_args.get("var_id")
        or request.view_args.get("cnv_id")
        or request.view_args.get("fus_id")
        or request.view_args.get("transloc_id")
    )

    form_data = request.form.to_dict()
    nomenclature, _variant = get_variant_nomenclature(form_data)
    _type = form_data.get("global", None)
    try:
        get_web_api_client().add_dna_variant_comment(
            sample_id=sample_id,
            target_id=id,
            form_data=form_data,
            headers=build_forward_headers(request.headers),
        )
        if _type == "global":
            flash("Global comment added", "green")
    except ApiRequestError as exc:
        app.logger.error("Failed to add comment via API for sample %s: %s", sample_id, exc)

    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=id))
    if nomenclature == "t":
        return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=id))
    if nomenclature == "cn":
        return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=id))

    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/hide_variant_comment", methods=["POST"])
@require("hide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def hide_variant_comment(sample_id: str, var_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().hide_dna_variant_comment(
            sample_id=sample_id,
            var_id=var_id,
            comment_id=comment_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to hide variant comment via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/unhide_variant_comment", methods=["POST"])
@require("unhide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def unhide_variant_comment(sample_id, var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().unhide_dna_variant_comment(
            sample_id=sample_id,
            var_id=var_id,
            comment_id=comment_id,
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to unhide variant comment via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<sample_id>/multi_class", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_snvs", min_role="user", min_level=9)
def classify_multi_variant(sample_id: str) -> Response:
    action = request.form.get("action")
    variants_to_modify = request.form.getlist("selected_object_id")
    assay_group = request.form.get("assay_group")
    subpanel = request.form.get("subpanel")
    tier = request.form.get("tier")
    irrelevant = request.form.get("irrelevant")
    false_positive = request.form.get("false_positive")

    if tier and action == "apply":
        try:
            get_web_api_client().set_dna_variants_tier_bulk(
                sample_id=sample_id,
                variant_ids=variants_to_modify,
                assay_group=assay_group,
                subpanel=subpanel,
                headers=build_forward_headers(request.headers),
            )
        except ApiRequestError as exc:
            app.logger.error(
                "Failed to bulk assign variant tier via API for sample %s: %s",
                sample_id,
                exc,
            )

    if false_positive:
        if action == "apply":
            try:
                get_web_api_client().set_dna_variants_false_positive_bulk(
                    sample_id=sample_id,
                    variant_ids=variants_to_modify,
                    apply=True,
                    headers=build_forward_headers(request.headers),
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to bulk mark variants false-positive via API for sample %s: %s",
                    sample_id,
                    exc,
                )
        elif action == "remove":
            try:
                get_web_api_client().set_dna_variants_false_positive_bulk(
                    sample_id=sample_id,
                    variant_ids=variants_to_modify,
                    apply=False,
                    headers=build_forward_headers(request.headers),
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to bulk unmark variants false-positive via API for sample %s: %s",
                    sample_id,
                    exc,
                )
    if irrelevant:
        if action == "apply":
            try:
                get_web_api_client().set_dna_variants_irrelevant_bulk(
                    sample_id=sample_id,
                    variant_ids=variants_to_modify,
                    apply=True,
                    headers=build_forward_headers(request.headers),
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to bulk mark variants irrelevant via API for sample %s: %s",
                    sample_id,
                    exc,
                )
        elif action == "remove":
            try:
                get_web_api_client().set_dna_variants_irrelevant_bulk(
                    sample_id=sample_id,
                    variant_ids=variants_to_modify,
                    apply=False,
                    headers=build_forward_headers(request.headers),
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to bulk unmark variants irrelevant via API for sample %s: %s",
                    sample_id,
                    exc,
                )
    return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
