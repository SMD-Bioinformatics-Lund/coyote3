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

"""DNA variant detail routes."""

from flask import Response, current_app as app, render_template

from coyote.blueprints.dna import dna_bp
from coyote.blueprints.dna.views_variants_common import raise_api_page_error
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


@dna_bp.route("/<string:sample_id>/var/<string:var_id>")
def show_variant(sample_id: str, var_id: str) -> Response | str:
    """
    Display detailed information for a specific DNA variant in a given sample.

    This view retrieves the variant and associated sample and assay configuration,
    gathers related data such as assay group, subpanel, and mappings, and prepares
    all necessary information for rendering the variant detail template.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response | str: Rendered HTML template displaying the variant details,
        or a redirect/response if the sample or configuration is not found.

    Side Effects:
        - May flash messages to the user if sample or configuration is missing.
        - May log information about the variant or related data.
    """
    try:
        payload = get_web_api_client().get_json(
            api_endpoints.dna_sample(sample_id, "variants", var_id),
            headers=forward_headers(),
        )
        app.logger.info("Loaded DNA variant detail from API service for sample %s", sample_id)
        return render_template(
            "show_variant_vep.html",
            variant=payload.variant,
            in_other=payload.in_other,
            annotations=payload.annotations,
            hidden_comments=payload.hidden_comments,
            latest_classification=payload.latest_classification,
            expression=payload.expression,
            civic=payload.civic,
            civic_gene=payload.civic_gene,
            oncokb=payload.oncokb,
            oncokb_action=payload.oncokb_action,
            oncokb_gene=payload.oncokb_gene,
            sample=payload.sample,
            brca_exchange=payload.brca_exchange,
            iarc_tp53=payload.iarc_tp53,
            assay_group=payload.assay_group,
            pon=payload.pon,
            other_classifications=payload.other_classifications,
            subpanel=payload.subpanel,
            sample_ids=payload.sample_ids,
            bam_id=payload.bam_id,
            annotations_interesting=payload.annotations_interesting,
            vep_var_class_translations=payload.vep_var_class_translations,
            vep_conseq_translations=payload.vep_conseq_translations,
            assay_group_mappings=payload.assay_group_mappings,
        )
    except ApiRequestError as exc:
        app.logger.error("DNA variant detail API fetch failed for sample %s: %s", sample_id, exc)
        raise_api_page_error(sample_id, "DNA variant detail", exc)
