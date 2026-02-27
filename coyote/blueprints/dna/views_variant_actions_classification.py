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

"""DNA variant action routes for classification operations."""

from __future__ import annotations

from flask import Response, redirect, request, url_for
from flask_login import login_required

from coyote.blueprints.dna import dna_bp
from coyote.blueprints.dna.views_variant_actions_common import (
    bulk_toggle,
    call_api,
    derive_nomenclature,
    headers,
    redirect_target,
    resolve_target_id,
)
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import get_web_api_client


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/classify", methods=["POST"], endpoint="classify_variant")
@dna_bp.route("/<string:sample_id>/fus/<string:fus_id>/classify", methods=["POST"], endpoint="classify_fusion")
@login_required
def classify_variant(sample_id: str, id: str | None = None) -> Response:
    target_id = id or resolve_target_id("var_id", "fus_id")
    form_data = request.form.to_dict()
    nomenclature = derive_nomenclature(form_data)
    call_api(
        sample_id,
        "Failed to classify variant via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "variants", "classify"),
            headers=headers(),
            json_body={"id": target_id, "form_data": form_data},
        ),
    )
    return redirect_target(sample_id, target_id, nomenclature)


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
    target_id = id or resolve_target_id("var_id", "fus_id")
    form_data = request.form.to_dict()
    nomenclature = derive_nomenclature(form_data)

    call_api(
        sample_id,
        "Failed to remove classification via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "variants", "rmclassify"),
            headers=headers(),
            json_body={"id": target_id, "form_data": form_data},
        ),
    )
    return redirect_target(sample_id, target_id, nomenclature)


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
        call_api(
            sample_id,
            "Failed to bulk assign variant tier via API",
            lambda: get_web_api_client().post_json(
                api_endpoints.dna_sample(sample_id, "variants", "bulk", "tier"),
                headers=headers(),
                json_body={
                    "variant_ids": variants_to_modify,
                    "assay_group": assay_group,
                    "subpanel": subpanel,
                    "tier": 3,
                },
            ),
        )

    bulk_toggle(
        sample_id=sample_id,
        enabled=false_positive,
        action=action,
        variant_ids=variants_to_modify,
        operation_label="false-positive",
        endpoint=api_endpoints.dna_sample(sample_id, "variants", "bulk", "fp"),
    )
    bulk_toggle(
        sample_id=sample_id,
        enabled=irrelevant,
        action=action,
        variant_ids=variants_to_modify,
        operation_label="irrelevant",
        endpoint=api_endpoints.dna_sample(sample_id, "variants", "bulk", "irrelevant"),
    )

    return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))
