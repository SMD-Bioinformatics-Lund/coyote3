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

"""
Views for handling RNA fusion cases in the Coyote3 application.
All routes require user authentication and appropriate sample access.
"""

from flask import current_app as app
from flask import (
    render_template,
    request,
    Response,
)

from coyote.blueprints.rna.forms import FusionFilter

from coyote.extensions import util
from coyote.blueprints.rna import rna_bp
from coyote.integrations.api.api_client import ApiRequestError, build_forward_headers, get_web_api_client
from copy import deepcopy


@rna_bp.route("/sample/<string:sample_id>", methods=["GET", "POST"])
def list_fusions(sample_id: str) -> str | Response:
    """
    Display and filter RNA fusion events for a given sample.

    This view handles both GET and POST requests to display fusion events
    for the specified sample. It supports dynamic filtering of fusions
    based on user input, manages sample group and assay configuration,
    and prepares data for rendering the fusion list template.

    Parameters:
        sample_id (str): The sample identifier.

    Returns:
        Response: Rendered HTML template for the fusion list page.
    """
    headers = build_forward_headers(request.headers)
    api_client = get_web_api_client()

    def _load_api_context():
        payload = api_client.get_rna_fusions(sample_id=sample_id, headers=headers)
        return payload

    try:
        fusions_payload = _load_api_context()
    except ApiRequestError as exc:
        app.logger.error("RNA fusion API fetch failed for sample %s: %s", sample_id, exc)
        return Response(str(exc), status=exc.status_code or 502)

    sample = fusions_payload.sample
    assay_config = fusions_payload.assay_config
    assay_config_schema = fusions_payload.assay_config_schema
    sample_has_filters = sample.get("filters", None)
    assay_group = fusions_payload.assay_group or assay_config.get("asp_group", "unknown")
    subpanel = fusions_payload.subpanel
    fusionlist_options = fusions_payload.fusionlist_options
    sample_filters = deepcopy(fusions_payload.filters)
    filter_context = deepcopy(fusions_payload.filter_context)
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    # Create the form
    form = FusionFilter()

    ###########################################################################
    ## FORM FILTERS ##
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        # Reset filters to defaults
        if form.reset.data:
            app.logger.info(f"Resetting filters to default settings for the sample {sample_id}")
            try:
                api_client.reset_sample_filters(
                    sample_id=sample_id,
                    headers=headers,
                )
            except ApiRequestError as exc:
                app.logger.error("Failed to reset RNA filters via API for sample %s: %s", sample_id, exc)
        else:
            filters_from_form = util.common.format_filters_from_form(form, assay_config_schema)
            filters_from_form["fusionlists"] = request.form.getlist("fusionlist_id")
            if sample.get("filters", {}).get("adhoc_genes"):
                filters_from_form["adhoc_genes"] = sample.get("filters", {}).get("adhoc_genes")
            try:
                api_client.update_sample_filters(
                    sample_id=sample_id,
                    filters=filters_from_form,
                    headers=headers,
                )
            except ApiRequestError as exc:
                app.logger.error("Failed to update RNA filters via API for sample %s: %s", sample_id, exc)

        try:
            fusions_payload = _load_api_context()
            sample = fusions_payload.sample
            assay_config = fusions_payload.assay_config
            assay_config_schema = fusions_payload.assay_config_schema
            sample_filters = deepcopy(fusions_payload.filters)
            filter_context = deepcopy(fusions_payload.filter_context)
            fusionlist_options = fusions_payload.fusionlist_options
        except ApiRequestError as exc:
            app.logger.error("RNA fusion API refresh failed for sample %s: %s", sample_id, exc)
            return Response(str(exc), status=exc.status_code or 502)

    if not sample_has_filters:
        try:
            api_client.reset_sample_filters(sample_id=sample_id, headers=headers)
            fusions_payload = _load_api_context()
            sample = fusions_payload.sample
            assay_config = fusions_payload.assay_config
            assay_config_schema = fusions_payload.assay_config_schema
            sample_filters = deepcopy(fusions_payload.filters)
            filter_context = deepcopy(fusions_payload.filter_context)
            fusionlist_options = fusions_payload.fusionlist_options
        except ApiRequestError as exc:
            app.logger.error("Failed to reset RNA filters via API for sample %s: %s", sample_id, exc)
    ############################################################################
    has_hidden_comments = fusions_payload.hidden_comments

    # Add them to the form and update with the requested settings
    form_data = deepcopy(sample_filters)
    form_data.update(
        {
            **{f"fusioncaller_{k}": True for k in filter_context["fusion_callers"]},
            **{f"fusioneffect_{k}": True for k in filter_context["fusion_effect_form_keys"]},
            **{f"fusionlist_{k}": True for k in filter_context["checked_fusionlists"]},
            **{assay_group: True},
        }
    )
    form.process(data=form_data)

    fusions = fusions_payload.fusions
    ai_text = fusions_payload.ai_text
    app.logger.info("Loaded RNA fusion list from API service for sample %s", sample_id)

    # Your logic for handling RNA samples
    return render_template(
        "list_fusions.html",
        sample=sample,
        form=form,
        fusions=fusions,
        fusionlist_options=fusionlist_options,
        checked_fusionlists=fusions_payload.checked_fusionlists,
        checked_fusionlists_dict=fusions_payload.checked_fusionlists_dict,
        hidden_comments=has_hidden_comments,
        ai_text=ai_text,
        sample_id=sample["_id"],
    )


@rna_bp.route("/<string:sample_id>/fusion/<string:fusion_id>")
def show_fusion(sample_id: str, fusion_id: str) -> Response | str:
    """
    Display details for a specific RNA fusion event.

    Retrieves the fusion by its ID, fetches the associated sample, obtains
    annotations and classification for the fusion, and renders the
    show_fusion.html template with this data.

    Args:
        sample_id (str): The unique identifier of the sample.
        fusion_id (str): The unique identifier of the fusion event.

    Returns:
        Response | str: Rendered HTML template for the fusion details page.
    """
    try:
        payload = get_web_api_client().get_rna_fusion(
            sample_id=sample_id,
            fusion_id=fusion_id,
            headers=build_forward_headers(request.headers),
        )
        app.logger.info("Loaded RNA fusion detail from API service for sample %s", sample_id)
        return render_template(
            "show_fusion.html",
            fusion=payload.fusion,
            in_other=payload.in_other,
            sample=payload.sample,
            annotations=payload.annotations,
            latest_classification=payload.latest_classification,
            annotations_interesting=payload.annotations_interesting,
            other_classifications=payload.other_classifications,
            hidden_comments=payload.hidden_comments,
            assay_group=payload.assay_group,
            subpanel=payload.subpanel,
            assay_group_mappings=payload.assay_group_mappings,
        )
    except ApiRequestError as exc:
        app.logger.error("RNA fusion detail API fetch failed for sample %s: %s", sample_id, exc)
        return Response(str(exc), status=exc.status_code or 502)
