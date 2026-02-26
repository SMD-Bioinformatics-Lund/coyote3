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

from coyote.extensions import store, util
from coyote.blueprints.rna import rna_bp
from coyote.util.decorators.access import require_sample_access
from coyote.util.misc import get_sample_and_assay_config
from coyote.services.interpretation.report_summary import generate_summary_text
from coyote.services.rna.helpers import create_fusioncallers, create_fusioneffectlist
from coyote.services.workflow.rna_workflow import RNAWorkflowService
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client
from copy import deepcopy


@rna_bp.route("/sample/<string:sample_id>", methods=["GET", "POST"])
@require_sample_access("sample_id")
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

    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    sample_has_filters = sample.get("filters", None)

    ## get the assay from the sample, fallback to the first group if not set
    sample_assay = sample.get("assay")

    # Get the profile from the sample, fallback to production if not set
    sample_profile = sample.get("profile", "production")

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get("asp_group", "unknown")  # myeloid, solid, lymphoid
    subpanel: str | None = sample.get("subpanel")  # breast, LP, lung, etc.
    analysis_sections = assay_config.get("analysis_types", [])
    display_sections_data = {}
    summary_sections_data = {}
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    # Get the entire genelist for the sample panel
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)

    # Get fusion lists for the sample panel (RNA-specific; list_type="fusionlist")
    fusionlist_options = store.isgl_handler.get_isgl_by_asp(
        sample_assay, is_active=True, list_type="fusionlist"
    )

    # Adding default fusion lists to RNA assay config if diagnosis-driven lists are enabled
    if assay_config.get("use_diagnosis_genelist", False) and subpanel:
        assay_default_config_fusionlist_ids = store.isgl_handler.get_isgl_ids(
            sample_assay, subpanel, "fusionlist", is_active=True
        )
        assay_config["filters"].setdefault("fusionlists", [])
        assay_config["filters"]["fusionlists"].extend(assay_default_config_fusionlist_ids)

    # Get filter settings from the sample and merge with assay config if sample does not have values
    sample, sample_filters = RNAWorkflowService.merge_and_normalize_sample_filters(
        sample, assay_config, sample_id, app.logger
    )

    # Update the sample filters with the default values from the assay config if the sample is new and does not have any filters set
    if not sample_has_filters:
        try:
            get_web_api_client().reset_sample_filters(
                sample_id=sample_id,
                headers=build_forward_headers(request.headers),
            )
        except ApiRequestError as exc:
            app.logger.error("Failed to reset RNA filters via API for sample %s: %s", sample_id, exc)

    # Create the form
    form = FusionFilter()

    ###########################################################################
    ## FORM FILTERS ##
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        _id = str(sample.get("_id"))
        # Reset filters to defaults
        if form.reset.data:
            app.logger.info(f"Resetting filters to default settings for the sample {sample_id}")
            try:
                get_web_api_client().reset_sample_filters(
                    sample_id=sample_id,
                    headers=build_forward_headers(request.headers),
                )
            except ApiRequestError as exc:
                app.logger.error("Failed to reset RNA filters via API for sample %s: %s", sample_id, exc)
        else:
            filters_from_form = util.common.format_filters_from_form(form, assay_config_schema)
            filters_from_form["fusionlists"] = request.form.getlist("fusionlist_id")
            filters_from_form["fusion_callers"] = create_fusioncallers(
                filters_from_form.get("fusion_callers", [])
            )
            filters_from_form["fusion_effects"] = create_fusioneffectlist(
                filters_from_form.get("fusion_effects", [])
            )
            if sample.get("filters", {}).get("adhoc_genes"):
                filters_from_form["adhoc_genes"] = sample.get("filters", {}).get("adhoc_genes")
            try:
                get_web_api_client().update_sample_filters(
                    sample_id=sample_id,
                    filters=filters_from_form,
                    headers=build_forward_headers(request.headers),
                )
            except ApiRequestError as exc:
                app.logger.error("Failed to update RNA filters via API for sample %s: %s", sample_id, exc)

        ## get sample again to receive updated forms!
        sample = store.sample_handler.get_sample_by_id(_id)
        sample, sample_filters = RNAWorkflowService.merge_and_normalize_sample_filters(
            sample, assay_config, sample_id, app.logger
        )
    ############################################################################
    # Check if sample has hidden comments
    has_hidden_comments = store.sample_handler.hidden_sample_comments(sample.get("_id"))

    filter_context = RNAWorkflowService.compute_filter_context(
        sample=sample,
        sample_filters=sample_filters,
        assay_panel_doc=assay_panel_doc,
    )

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

    try:
        api_payload = get_web_api_client().get_rna_fusions(
            sample_id=sample_id,
            headers=build_forward_headers(request.headers),
        )
        fusions = api_payload.fusions
        summary_sections_data["fusions"] = api_payload.meta.get("tiered", [])
        app.logger.info("Loaded RNA fusion list from API service for sample %s", sample_id)
    except ApiRequestError as exc:
        app.logger.error("RNA fusion API fetch failed for sample %s: %s", sample_id, exc)
        return Response(str(exc), status=exc.status_code or 502)

    # TODO: load them as a display_sections_data instead of attaching to sample
    sample = RNAWorkflowService.attach_rna_analysis_sections(sample)

    # AI summary suggestion text for "Suggest" button, aligned with DNA flow.
    ai_text = generate_summary_text(
        sample_ids,
        assay_config,
        assay_panel_doc,
        summary_sections_data,
        filter_context["filter_genes"],
        filter_context["checked_fusionlists"],
    )

    # Your logic for handling RNA samples
    return render_template(
        "list_fusions.html",
        sample=sample,
        form=form,
        fusions=fusions,
        fusionlist_options=fusionlist_options,
        checked_fusionlists=filter_context["checked_fusionlists"],
        checked_fusionlists_dict=filter_context["genes_covered_in_panel"],
        hidden_comments=has_hidden_comments,
        ai_text=ai_text,
        sample_id=sample["_id"],
    )


@rna_bp.route("/<string:sample_id>/fusion/<string:fusion_id>")
@require_sample_access("sample_id")
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
