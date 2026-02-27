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

"""DNA variant list routes."""

from copy import deepcopy

from flask import Response, current_app as app, render_template, request
from wtforms import BooleanField

from coyote.blueprints.dna import dna_bp
from coyote.blueprints.dna.forms import DNAFilterForm
from coyote.blueprints.dna.views_variants_common import raise_api_page_error
from coyote.extensions import util
from coyote.integrations.api import endpoints as api_endpoints
from coyote.integrations.api.api_client import ApiRequestError, forward_headers, get_web_api_client


@dna_bp.route("/sample/<string:sample_id>", methods=["GET", "POST"])
def list_variants(sample_id: str) -> Response | str:
    """
    Displays a list of DNA variants for a given sample.

    Args:
        sample_id (str): The unique identifier of the sample.

    Returns:
        Response | str: Rendered HTML template displaying the variants for the sample,
        or a redirect/response if the sample or configuration is not found.

    Side Effects:
        - Flashes messages to the user if sample or assay configuration is missing.
        - Logs information about selected OncoKB genes.
    """
    headers = forward_headers()
    api_client = get_web_api_client()

    def _load_api_context():
        return api_client.get_json(
            api_endpoints.dna_sample(sample_id, "variants"),
            headers=headers,
        )

    try:
        variants_payload = _load_api_context()
        app.logger.info("Loaded DNA variant list from API service for sample %s", sample_id)
    except ApiRequestError as exc:
        app.logger.error("DNA variant API fetch failed for sample %s: %s", sample_id, exc)
        raise_api_page_error(sample_id, "DNA variants", exc)

    sample = variants_payload.sample
    assay_config = variants_payload.assay_config
    assay_config_schema = variants_payload.assay_config_schema
    sample_has_filters = sample.get("filters", None)
    sample_filters = deepcopy(variants_payload.filters)
    sample_ids = variants_payload.sample_ids
    assay_group = variants_payload.assay_group or assay_config.get("asp_group", "unknown")
    subpanel = variants_payload.subpanel
    analysis_sections = variants_payload.analysis_sections
    display_sections_data = deepcopy(variants_payload.display_sections_data)
    ai_text = variants_payload.ai_text
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    insilico_panel_genelists = variants_payload.assay_panels
    all_panel_genelist_names = variants_payload.all_panel_genelist_names
    checked_genelists = variants_payload.checked_genelists
    genes_covered_in_panel = variants_payload.checked_genelists_dict
    verification_sample_used = variants_payload.verification_sample_used

    if not sample_has_filters:
        try:
            api_client.post_json(
                api_endpoints.sample(sample_id, "filters", "reset"),
                headers=headers,
            )
            variants_payload = _load_api_context()
            sample = variants_payload.sample
            sample_filters = deepcopy(variants_payload.filters)
            display_sections_data = deepcopy(variants_payload.display_sections_data)
            ai_text = variants_payload.ai_text
            checked_genelists = variants_payload.checked_genelists
            genes_covered_in_panel = variants_payload.checked_genelists_dict
            verification_sample_used = variants_payload.verification_sample_used
        except ApiRequestError as exc:
            app.logger.error("Failed to reset DNA filters via API for sample %s: %s", sample_id, exc)

    if all_panel_genelist_names:
        for gene_list in all_panel_genelist_names:
            setattr(DNAFilterForm, f"genelist_{gene_list}", BooleanField())

    form = DNAFilterForm()

    if request.method == "POST" and form.validate_on_submit():
        if form.reset.data:
            app.logger.info(f"Resetting filters to default settings for the sample {sample_id}")
            try:
                api_client.post_json(
                    api_endpoints.sample(sample_id, "filters", "reset"),
                    headers=headers,
                )
            except ApiRequestError as exc:
                app.logger.error("Failed to reset DNA filters via API for sample %s: %s", sample_id, exc)
        else:
            filters_from_form = util.common.format_filters_from_form(form, assay_config_schema)
            if sample.get("filters", {}).get("adhoc_genes"):
                filters_from_form["adhoc_genes"] = sample.get("filters", {}).get("adhoc_genes")
            try:
                api_client.post_json(
                    api_endpoints.sample(sample_id, "filters", "update"),
                    headers=headers,
                    json_body={"filters": filters_from_form},
                )
            except ApiRequestError as exc:
                app.logger.error("Failed to update DNA filters via API for sample %s: %s", sample_id, exc)

        try:
            variants_payload = _load_api_context()
            sample = variants_payload.sample
            assay_config = variants_payload.assay_config
            assay_config_schema = variants_payload.assay_config_schema
            sample_filters = deepcopy(variants_payload.filters)
            sample_ids = variants_payload.sample_ids
            assay_group = variants_payload.assay_group or assay_config.get("asp_group", "unknown")
            subpanel = variants_payload.subpanel
            analysis_sections = variants_payload.analysis_sections
            display_sections_data = deepcopy(variants_payload.display_sections_data)
            ai_text = variants_payload.ai_text
            insilico_panel_genelists = variants_payload.assay_panels
            checked_genelists = variants_payload.checked_genelists
            genes_covered_in_panel = variants_payload.checked_genelists_dict
            verification_sample_used = variants_payload.verification_sample_used
        except ApiRequestError as exc:
            app.logger.error("DNA variant API refresh failed for sample %s: %s", sample_id, exc)
            raise_api_page_error(sample_id, "DNA variants", exc)

    has_hidden_comments = variants_payload.hidden_comments

    form_data = deepcopy(sample_filters)
    form_data.update(
        {
            **{f"vep_{k}": True for k in sample_filters.get("vep_consequences", [])},
            **{f"cnveffect_{k}": True for k in sample_filters.get("cnveffects", [])},
            **{f"genelist_{k}": True for k in checked_genelists},
            **{assay_group: True},
        }
    )
    form.process(data=form_data)

    bam_id = variants_payload.bam_id
    vep_variant_class_meta = variants_payload.vep_var_class_translations
    vep_conseq_meta = variants_payload.vep_conseq_translations
    oncokb_genes = variants_payload.oncokb_genes

    app.logger.info(f"oncokb_selected_genes : {oncokb_genes} ")

    return render_template(
        "list_variants_vep.html",
        sample=sample,
        sample_ids=sample_ids,
        assay_group=assay_group,
        analysis_sections=analysis_sections,
        display_sections_data=display_sections_data,
        assay_panels=insilico_panel_genelists,
        checked_genelists_dict=genes_covered_in_panel,
        hidden_comments=has_hidden_comments,
        vep_var_class_translations=vep_variant_class_meta,
        vep_conseq_translations=vep_conseq_meta,
        bam_id=bam_id,
        form=form,
        ai_text=ai_text,
        verification_sample_used=verification_sample_used,
        oncokb_genes=oncokb_genes,
    )
