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

"""DNA variant action routes for per-variant flag operations."""

from flask import Response, redirect, url_for
from flask_login import login_required

from coyote.blueprints.dna import dna_bp
from coyote.blueprints.dna.views_variant_actions_common import call_api, headers
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import get_web_api_client


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/unfp", methods=["POST"])
@login_required
def unmark_false_variant(sample_id: str, var_id: str) -> Response:
    call_api(
        sample_id,
        "Failed to unmark variant false-positive via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "variants", var_id, "unfp"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/fp", methods=["POST"])
@login_required
def mark_false_variant(sample_id: str, var_id: str) -> Response:
    call_api(
        sample_id,
        "Failed to mark variant false-positive via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "variants", var_id, "fp"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/uninterest", methods=["POST"])
@login_required
def unmark_interesting_variant(sample_id: str, var_id: str) -> Response:
    call_api(
        sample_id,
        "Failed to unmark variant interesting via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "variants", var_id, "uninterest"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/interest", methods=["POST"])
@login_required
def mark_interesting_variant(sample_id: str, var_id: str) -> Response:
    call_api(
        sample_id,
        "Failed to mark variant interesting via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "variants", var_id, "interest"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/relevant", methods=["POST"])
@login_required
def unmark_irrelevant_variant(sample_id: str, var_id: str) -> Response:
    call_api(
        sample_id,
        "Failed to unmark variant irrelevant via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "variants", var_id, "relevant"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/irrelevant", methods=["POST"])
@login_required
def mark_irrelevant_variant(sample_id: str, var_id: str) -> Response:
    call_api(
        sample_id,
        "Failed to mark variant irrelevant via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "variants", var_id, "irrelevant"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/blacklist", methods=["POST"])
@login_required
def add_variant_to_blacklist(sample_id: str, var_id: str) -> Response:
    call_api(
        sample_id,
        "Failed to blacklist variant via API",
        lambda: get_web_api_client().post_json(
            api_endpoints.dna_sample(sample_id, "variants", var_id, "blacklist"),
            headers=headers(),
        ),
    )
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id))
