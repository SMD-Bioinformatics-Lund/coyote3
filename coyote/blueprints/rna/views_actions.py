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

"""RNA fusion action routes."""

from flask import Response, current_app as app, flash, redirect, request, url_for

from coyote.blueprints.rna import rna_bp
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


@rna_bp.route("/<string:sample_id>/fusion/fp/<string:fus_id>", methods=["POST"])
def mark_false_fusion(sample_id: str, fus_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fus_id}/fp",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to mark RNA fusion false-positive via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/unfp/<string:fus_id>", methods=["POST"])
def unmark_false_fusion(sample_id: str, fus_id: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fus_id}/unfp",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error(
            "Failed to unmark RNA fusion false-positive via API for sample %s: %s", sample_id, exc
        )
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route(
    "/<string:sample_id>/fusion/pickfusioncall/<string:fus_id>/<string:callidx>/<string:num_calls>",
    methods=["GET", "POST"],
)
def pick_fusioncall(sample_id: str, fus_id: str, callidx: str, num_calls: str) -> Response:
    try:
        get_web_api_client().post_json(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fus_id}/pick/{callidx}/{num_calls}",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to pick RNA fusion call via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/hide_fusion_comment/<string:fus_id>", methods=["POST"])
def hide_fusion_comment(sample_id: str, fus_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().post_json(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fus_id}/comments/{comment_id}/hide",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to hide RNA fusion comment via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/unhide_fusion_comment/<string:fus_id>", methods=["POST"])
def unhide_fusion_comment(sample_id: str, fus_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    try:
        get_web_api_client().post_json(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fus_id}/comments/{comment_id}/unhide",
            headers=forward_headers(),
        )
    except ApiRequestError as exc:
        app.logger.error("Failed to unhide RNA fusion comment via API for sample %s: %s", sample_id, exc)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/multi_class/<sample_id>", methods=["POST"])
def classify_multi_variant(sample_id: str) -> Response:
    action = request.form.get("action")

    variants_to_modify = request.form.getlist("selected_object_id")
    tier = request.form.get("tier", None)
    irrelevant = request.form.get("irrelevant", None)
    false_positive = request.form.get("false_positive", None)

    if tier and action == "apply":
        flash(
            "Bulk tier assignment is not supported for RNA fusions. Use fusion detail page.",
            "yellow",
        )
    elif false_positive:
        if action == "apply":
            try:
                get_web_api_client().post_json(
                    f"/api/v1/rna/samples/{sample_id}/fusions/bulk/fp",
                    headers=forward_headers(),
                    params={"apply": "true", "fusion_ids": variants_to_modify},
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to bulk mark RNA fusions false-positive via API for sample %s: %s",
                    sample_id,
                    exc,
                )
        elif action == "remove":
            try:
                get_web_api_client().post_json(
                    f"/api/v1/rna/samples/{sample_id}/fusions/bulk/fp",
                    headers=forward_headers(),
                    params={"apply": "false", "fusion_ids": variants_to_modify},
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to bulk unmark RNA fusions false-positive via API for sample %s: %s",
                    sample_id,
                    exc,
                )
    elif irrelevant:
        if action == "apply":
            try:
                get_web_api_client().post_json(
                    f"/api/v1/rna/samples/{sample_id}/fusions/bulk/irrelevant",
                    headers=forward_headers(),
                    params={"apply": "true", "fusion_ids": variants_to_modify},
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to bulk mark RNA fusions irrelevant via API for sample %s: %s",
                    sample_id,
                    exc,
                )
        elif action == "remove":
            try:
                get_web_api_client().post_json(
                    f"/api/v1/rna/samples/{sample_id}/fusions/bulk/irrelevant",
                    headers=forward_headers(),
                    params={"apply": "false", "fusion_ids": variants_to_modify},
                )
            except ApiRequestError as exc:
                app.logger.error(
                    "Failed to bulk unmark RNA fusions irrelevant via API for sample %s: %s",
                    sample_id,
                    exc,
                )
    return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))
