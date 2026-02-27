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

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from flask import Response, current_app as app, flash, redirect, request, url_for
from flask_login import login_required

from coyote.blueprints.dna import dna_bp
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


def _headers() -> dict[str, str]:
    return forward_headers()


def _call_api(sample_id: str, log_message: str, api_call: Callable[[], Any]) -> bool:
    try:
        api_call()
        return True
    except ApiRequestError as exc:
        app.logger.error("%s for sample %s: %s", log_message, sample_id, exc)
        return False


def _resolve_target_id(*keys: str) -> str:
    for key in keys:
        value = request.view_args.get(key)
        if value:
            return value
    return ""


def _derive_nomenclature(form_data: dict[str, Any]) -> str:
    if form_data.get("fusionpoints"):
        return "f"
    if form_data.get("translocpoints"):
        return "t"
    if form_data.get("cnvvar"):
        return "cn"
    return "p"


def _redirect_target(sample_id: str, target_id: str, nomenclature: str) -> Response:
    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=target_id))
    if nomenclature == "t":
        return redirect(url_for("dna_bp.show_transloc", sample_id=sample_id, transloc_id=target_id))
    if nomenclature == "cn":
        return redirect(url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=target_id))
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=target_id))


def _bulk_toggle(
    sample_id: str,
    enabled: str | None,
    action: str | None,
    variant_ids: list[str],
    operation_label: str,
    endpoint: str,
) -> None:
    if not enabled or action not in {"apply", "remove"}:
        return

    apply = action == "apply"
    verb = "mark" if apply else "unmark"
    _call_api(
        sample_id,
        f"Failed to bulk {verb} variants {operation_label} via API",
        lambda: get_web_api_client().post_json(
            endpoint,
            headers=_headers(),
            params={"apply": str(apply).lower(), "variant_ids": variant_ids},
        ),
    )


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/unfp", methods=["POST"])
@login_required
def unmark_false_variant(sample_id: str, var_id: str) -> Response:
    _call_api(
        sample_id,
        "Failed to unmark variant false-positive via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/unfp",
            headers=_headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/fp", methods=["POST"])
@login_required
def mark_false_variant(sample_id: str, var_id: str) -> Response:
    _call_api(
        sample_id,
        "Failed to mark variant false-positive via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/fp",
            headers=_headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/uninterest", methods=["POST"])
@login_required
def unmark_interesting_variant(sample_id: str, var_id: str) -> Response:
    _call_api(
        sample_id,
        "Failed to unmark variant interesting via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/uninterest",
            headers=_headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/interest", methods=["POST"])
@login_required
def mark_interesting_variant(sample_id: str, var_id: str) -> Response:
    _call_api(
        sample_id,
        "Failed to mark variant interesting via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/interest",
            headers=_headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/relevant", methods=["POST"])
@login_required
def unmark_irrelevant_variant(sample_id: str, var_id: str) -> Response:
    _call_api(
        sample_id,
        "Failed to unmark variant irrelevant via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/relevant",
            headers=_headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/irrelevant", methods=["POST"])
@login_required
def mark_irrelevant_variant(sample_id: str, var_id: str) -> Response:
    _call_api(
        sample_id,
        "Failed to mark variant irrelevant via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/irrelevant",
            headers=_headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/blacklist", methods=["POST"])
@login_required
def add_variant_to_blacklist(sample_id: str, var_id: str) -> Response:
    _call_api(
        sample_id,
        "Failed to blacklist variant via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/blacklist",
            headers=_headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/classify", methods=["POST"], endpoint="classify_variant")
@dna_bp.route("/<string:sample_id>/fus/<string:fus_id>/classify", methods=["POST"], endpoint="classify_fusion")
@login_required
def classify_variant(sample_id: str, id: str | None = None) -> Response:
    target_id = id or _resolve_target_id("var_id", "fus_id")
    form_data = request.form.to_dict()
    nomenclature = _derive_nomenclature(form_data)
    _call_api(
        sample_id,
        "Failed to classify variant via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/classify",
            headers=_headers(),
            json_body={"id": target_id, "form_data": form_data},
        ),
    )
    return _redirect_target(sample_id, target_id, nomenclature)


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
@login_required
def remove_classified_variant(sample_id: str, id: str | None = None) -> Response:
    target_id = id or _resolve_target_id("var_id", "fus_id")
    form_data = request.form.to_dict()
    nomenclature = _derive_nomenclature(form_data)

    _call_api(
        sample_id,
        "Failed to remove classification via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/rmclassify",
            headers=_headers(),
            json_body={"id": target_id, "form_data": form_data},
        ),
    )
    return _redirect_target(sample_id, target_id, nomenclature)


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
@login_required
def add_var_comment(sample_id: str, id: str | None = None, **kwargs: Any) -> Response:
    _ = kwargs
    target_id = id or _resolve_target_id("var_id", "cnv_id", "fus_id", "transloc_id")

    form_data = request.form.to_dict()
    nomenclature = _derive_nomenclature(form_data)
    comment_scope = form_data.get("global")

    call_ok = _call_api(
        sample_id,
        "Failed to add comment via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/comments/add",
            headers=_headers(),
            json_body={"id": target_id, "form_data": form_data},
        ),
    )
    if call_ok and comment_scope == "global":
        flash("Global comment added", "green")

    return _redirect_target(sample_id, target_id, nomenclature)


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/hide_variant_comment", methods=["POST"])
@login_required
def hide_variant_comment(sample_id: str, var_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    _call_api(
        sample_id,
        "Failed to hide variant comment via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/hide",
            headers=_headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/unhide_variant_comment", methods=["POST"])
@login_required
def unhide_variant_comment(sample_id: str, var_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    _call_api(
        sample_id,
        "Failed to unhide variant comment via API",
        lambda: get_web_api_client().post_json(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/unhide",
            headers=_headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<sample_id>/multi_class", methods=["POST"])
@login_required
def classify_multi_variant(sample_id: str) -> Response:
    action = request.form.get("action")
    variants_to_modify = request.form.getlist("selected_object_id")
    assay_group = request.form.get("assay_group")
    subpanel = request.form.get("subpanel")
    tier = request.form.get("tier")
    irrelevant = request.form.get("irrelevant")
    false_positive = request.form.get("false_positive")

    if tier and action == "apply":
        _call_api(
            sample_id,
            "Failed to bulk assign variant tier via API",
            lambda: get_web_api_client().post_json(
                f"/api/v1/dna/samples/{sample_id}/variants/bulk/tier",
                headers=_headers(),
                json_body={
                    "variant_ids": variants_to_modify,
                    "assay_group": assay_group,
                    "subpanel": subpanel,
                    "tier": 3,
                },
            ),
        )

    _bulk_toggle(
        sample_id=sample_id,
        enabled=false_positive,
        action=action,
        variant_ids=variants_to_modify,
        operation_label="false-positive",
        endpoint=f"/api/v1/dna/samples/{sample_id}/variants/bulk/fp",
    )
    _bulk_toggle(
        sample_id=sample_id,
        enabled=irrelevant,
        action=action,
        variant_ids=variants_to_modify,
        operation_label="irrelevant",
        endpoint=f"/api/v1/dna/samples/{sample_id}/variants/bulk/irrelevant",
    )

    return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
