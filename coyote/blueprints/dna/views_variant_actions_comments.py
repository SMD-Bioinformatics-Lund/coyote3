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

"""DNA variant action routes for comment add/hide/unhide operations."""

from __future__ import annotations

from typing import Any

from flask import Response, flash, redirect, request, url_for
from flask_login import login_required

from coyote.blueprints.dna import dna_bp
from coyote.blueprints.dna.views_variant_actions_common import (
    call_api,
    derive_nomenclature,
    headers,
    redirect_target,
    resolve_target_id,
)
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import get_web_api_client


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
    target_id = id or resolve_target_id("var_id", "cnv_id", "fus_id", "transloc_id")

    form_data = request.form.to_dict()
    nomenclature = derive_nomenclature(form_data)
    comment_scope = form_data.get("global")

    call_ok = call_api(
        sample_id,
        "Failed to add comment via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "comments", "add"),
            headers=headers(),
            json_body={"id": target_id, "form_data": form_data},
        ),
    )
    if call_ok and comment_scope == "global":
        flash("Global comment added", "green")

    return redirect_target(sample_id, target_id, nomenclature)


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/hide_variant_comment", methods=["POST"])
@login_required
def hide_variant_comment(sample_id: str, var_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    call_api(
        sample_id,
        "Failed to hide variant comment via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "variants", var_id, "comments", comment_id, "hide"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/unhide_variant_comment", methods=["POST"])
@login_required
def unhide_variant_comment(sample_id: str, var_id: str) -> Response:
    comment_id = request.form.get("comment_id", "MISSING_ID")
    call_api(
        sample_id,
        "Failed to unhide variant comment via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(
                sample_id, "variants", var_id, "comments", comment_id, "unhide"
            ),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))
