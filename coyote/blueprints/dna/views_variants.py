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
Views for DNA variant, CNV, translocation, and biomarker management and reporting in the Coyote3 genomic analysis framework.
"""

from flask import current_app as app
from flask import (
    redirect,
    render_template,
    request,
    url_for,
    send_from_directory,
    flash,
    send_file,
    Response,
)
from copy import deepcopy
from wtforms import BooleanField
from coyote.extensions import util
from coyote.blueprints.dna import dna_bp
from coyote.blueprints.dna.forms import DNAFilterForm
from coyote.integrations.api.api_client import ApiRequestError, build_forward_headers, get_web_api_client
from coyote.errors.exceptions import AppError
from PIL import Image
import os
import io


def _raise_api_page_error(sample_id: str, page: str, exc: ApiRequestError) -> None:
    raise AppError(
        status_code=exc.status_code or 502,
        message=f"Failed to load {page}.",
        details=f"Sample {sample_id}: {exc}",
    )


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
    headers = build_forward_headers(request.headers)
    api_client = get_web_api_client()

    def _load_api_context():
        return api_client.get_json(
            f"/api/v1/dna/samples/{sample_id}/variants",
            headers=headers,
        )

    try:
        variants_payload = _load_api_context()
        app.logger.info("Loaded DNA variant list from API service for sample %s", sample_id)
    except ApiRequestError as exc:
        app.logger.error("DNA variant API fetch failed for sample %s: %s", sample_id, exc)
        _raise_api_page_error(sample_id, "DNA variants", exc)

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
                f"/api/v1/samples/{sample_id}/filters/reset",
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

    # Inherit DNAFilterForm, pass all genepanels from mongodb, set as boolean, NOW IT IS DYNAMIC!
    if all_panel_genelist_names:
        for gene_list in all_panel_genelist_names:
            setattr(DNAFilterForm, f"genelist_{gene_list}", BooleanField())

    # Create the form
    form = DNAFilterForm()

    ###########################################################################
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        # Reset filters to defaults
        if form.reset.data:
            app.logger.info(f"Resetting filters to default settings for the sample {sample_id}")
            try:
                api_client.post_json(
                    f"/api/v1/samples/{sample_id}/filters/reset",
                    headers=headers,
                )
            except ApiRequestError as exc:
                app.logger.error("Failed to reset DNA filters via API for sample %s: %s", sample_id, exc)
        else:
            filters_from_form = util.common.format_filters_from_form(form, assay_config_schema)
            # if there are any adhoc genes for the sample, add them to the form data before saving
            if sample.get("filters", {}).get("adhoc_genes"):
                filters_from_form["adhoc_genes"] = sample.get("filters", {}).get("adhoc_genes")
            try:
                api_client.post_json(
                    f"/api/v1/samples/{sample_id}/filters/update",
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
            _raise_api_page_error(sample_id, "DNA variants", exc)

    ############################################################################

    has_hidden_comments = variants_payload.hidden_comments

    # Add them to the form and update with the requested settings
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


@dna_bp.route("/<string:sample_id>/plot/<string:fn>", endpoint="show_any_plot")  # type: ignore
@dna_bp.route("/<string:sample_id>/plot/rotated/<string:fn>", endpoint="show_any_plot_rotated")  # type: ignore
def show_any_plot(sample_id: str, fn: str, angle: int = 90) -> Response | str:
    """
    Displays a plot image for a given sample.

    Args:
        sample_id (str): The unique identifier of the sample.
        fn (str): The filename of the plot image to display.
        angle (int, optional): The angle to rotate the image, defaults to 90.

    Returns:
        flask.Response | str: The image file as a response, or an error message.
    """
    try:
        payload = get_web_api_client().get_json(
            f"/api/v1/dna/samples/{sample_id}/plot_context",
            headers=build_forward_headers(request.headers),
        )
    except ApiRequestError as exc:
        app.logger.error("DNA plot context API fetch failed for sample %s: %s", sample_id, exc)
        flash("Failed to load sample context for plot", "red")
        return redirect(url_for("home_bp.samples_home"))

    assay_config = payload.assay_config
    base_dir = payload.plots_base_dir or assay_config.get("reporting", {}).get("plots_path", None)

    if base_dir:
        file_path = os.path.join(base_dir, fn)
        if not os.path.exists(file_path):
            flash(f"File not found: {file_path}", "red")
            return request.url

    if request.endpoint == "dna_bp.show_any_plot_rotated":
        # Rotate the image by the specified angle (default is 90 degrees)
        try:
            with Image.open(os.path.join(base_dir, fn)) as img:
                rotated_img = img.rotate(-angle, expand=True)
                img_io = io.BytesIO()
                rotated_img.save(img_io, format="PNG")
                img_io.seek(0)
                return send_file(img_io, mimetype="image/png")
        except Exception as e:
            app.logger.error(f"Error rotating image: {e}")
            flash("Error processing image", "red")
            return request.url

    return send_from_directory(base_dir, fn)


## Individual variant view ##
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
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}",
            headers=build_forward_headers(request.headers),
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
        _raise_api_page_error(sample_id, "DNA variant detail", exc)
