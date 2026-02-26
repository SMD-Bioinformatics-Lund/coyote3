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
from pprint import pformat
from copy import deepcopy
from wtforms import BooleanField
from coyote.extensions import store, util
from coyote.blueprints.dna import dna_bp
from coyote.blueprints.dna import filters as dna_template_filters
from coyote.blueprints.dna.varqueries import build_query
from coyote.blueprints.dna.cnvqueries import build_cnv_query
from coyote.blueprints.dna.forms import DNAFilterForm
from coyote.util.decorators.access import require_sample_access
from coyote.util.misc import get_sample_and_assay_config
from coyote.services.interpretation.annotation_enrichment import (
    add_alt_class,
    add_global_annotations,
)
from coyote.services.interpretation.report_summary import (
    generate_summary_text,
)
from coyote.services.dna.dna_filters import (
    cnv_organizegenes,
    cnvtype_variant,
    create_cnveffectlist,
    get_filter_conseq_terms,
)
from coyote.services.dna.dna_reporting import hotspot_variant
from coyote.services.dna.dna_variants import format_pon
from coyote.services.workflow.dna_workflow import DNAWorkflowService
from coyote_web.api_client import ApiRequestError, build_forward_headers, get_web_api_client
from PIL import Image
import os
import io


@dna_bp.route("/sample/<string:sample_id>", methods=["GET", "POST"])
@require_sample_access("sample_id")
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
    # Find sample data by name
    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result
    DNAWorkflowService.validate_report_inputs(app.logger, sample, assay_config)

    # sample = store.sample_handler.get_sample(sample_id)  # sample_id = name/id
    sample_has_filters = sample.get("filters", None)

    # Get case and control samples
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    if not sample_ids:
        sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))

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
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    # Get the entire genelist for the sample panel
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)

    # Get the genelists for the sample panel
    insilico_panel_genelists = store.isgl_handler.get_isgl_by_asp(sample_assay, is_active=True)
    all_panel_genelist_names = util.common.get_assay_genelist_names(insilico_panel_genelists)

    # Adding the default gene lists to the assay_config, if the use_diagnosis_genelist is set to true
    if assay_config.get("use_diagnosis_genelist", False) and subpanel:
        assay_default_config_genelist_ids = store.isgl_handler.get_isgl_ids(
            sample_assay, subpanel, "genelist", is_active=True
        )
        assay_config["filters"]["genelists"].extend(assay_default_config_genelist_ids)

    # Get filter settings from the sample and merge with assay config if sample does not have values
    sample = util.common.merge_sample_settings_with_assay_config(sample, assay_config)
    sample_filters = deepcopy(sample.get("filters", {}))

    # Update the sample filters with the default values from the assay config if the sample is new and does not have any filters set
    if not sample_has_filters:
        store.sample_handler.reset_sample_settings(sample["_id"], assay_config.get("filters"))

    # Inherit DNAFilterForm, pass all genepanels from mongodb, set as boolean, NOW IT IS DYNAMIC!
    if all_panel_genelist_names:
        for gene_list in all_panel_genelist_names:
            setattr(DNAFilterForm, f"genelist_{gene_list}", BooleanField())

    # Create the form
    form = DNAFilterForm()

    ###########################################################################
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        _id = str(sample.get("_id"))
        # Reset filters to defaults
        if form.reset.data:
            app.logger.info(f"Resetting filters to default settings for the sample {sample_id}")
            store.sample_handler.reset_sample_settings(_id, assay_config.get("filters", {}))
        else:
            filters_from_form = util.common.format_filters_from_form(form, assay_config_schema)
            # if there are any adhoc genes for the sample, add them to the form data before saving
            if sample.get("filters", {}).get("adhoc_genes"):
                filters_from_form["adhoc_genes"] = sample.get("filters", {}).get("adhoc_genes")
            store.sample_handler.update_sample_filters(_id, filters_from_form)

        ## get sample again to receive updated forms!
        sample = store.sample_handler.get_sample_by_id(_id)
        sample_filters = deepcopy(sample.get("filters"))

    ############################################################################

    # Check if the sample has hidden comments
    has_hidden_comments = store.sample_handler.hidden_sample_comments(sample.get("_id"))

    # sample filters, either set, or default
    cnv_effects = sample_filters.get("cnveffects", [])

    # Get the genes covered in the panel and effective filter set of genes
    checked_genelists = sample_filters.get("genelists", [])
    checked_genelists_genes_dict: list[dict] = store.isgl_handler.get_isgl_by_ids(checked_genelists)
    genes_covered_in_panel, filter_genes = util.common.get_sample_effective_genes(
        sample, assay_panel_doc, checked_genelists_genes_dict
    )

    filter_conseq = get_filter_conseq_terms(sample_filters.get("vep_consequences", []))
    filter_cnveffects = create_cnveffectlist(cnv_effects)

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

    # this is in config, but needs to be tested (2024-05-14) with a HD-sample of relevant name
    disp_pos = []
    verification_sample_used = None
    if assay_config.get("verification_samples"):
        verification_samples = assay_config.get("verification_samples")
        for veri_key, veri_value in verification_samples.items():
            if veri_key in sample["name"]:
                disp_pos = verification_samples[veri_key]
                verification_sample_used = veri_key

    ## SNV FILTRATION STARTS HERE ! ##
    ##################################
    ## The query should really be constructed according to some configured rules for a specific assay
    use_api_variants = bool(app.config.get("WEB_API_READ_DNA_VARIANTS", False)) and request.method == "GET"
    variants = []
    tiered_variants = []
    if use_api_variants:
        try:
            api_payload = get_web_api_client().get_dna_variants(
                sample_id=sample_id,
                headers=build_forward_headers(request.headers),
            )
            variants = api_payload.variants
            tiered_variants = api_payload.meta.get("tiered", [])
            app.logger.info("Loaded DNA variant list from API service for sample %s", sample_id)
        except ApiRequestError as exc:
            app.logger.warning("DNA variant API fetch failed for sample %s: %s", sample_id, exc)
            if app.config.get("WEB_API_STRICT_MODE", False):
                return Response(str(exc), status=exc.status_code or 502)

    if not variants:
        query = build_query(
            assay_group,
            {
                "id": str(sample["_id"]),
                "max_freq": sample_filters["max_freq"],
                "min_freq": sample_filters["min_freq"],
                "max_control_freq": sample_filters["max_control_freq"],
                "min_depth": sample_filters["min_depth"],
                "min_alt_reads": sample_filters["min_alt_reads"],
                "max_popfreq": sample_filters["max_popfreq"],
                "filter_conseq": filter_conseq,
                "filter_genes": filter_genes,
                "disp_pos": disp_pos,
            },
        )

        variants_iter = store.variant_handler.get_case_variants(query)
        variants = list(variants_iter)

        # Add blacklist data
        variants = store.blacklist_handler.add_blacklist_data(variants, assay_group)

        # Add global annotations for the variants
        variants, tiered_variants = add_global_annotations(variants, assay_group, subpanel)

        # Add hotspot data
        variants = hotspot_variant(variants)
        app.logger.info("Loaded DNA variant list from Mongo for sample %s", sample_id)

    summary_sections_data["snvs"] = tiered_variants

    display_sections_data["snvs"] = deepcopy(variants)

    ### SNV FILTRATION ENDS HERE ###

    ## GET Other sections CNVs TRANSLOCS and OTHER BIOMARKERS ##
    if "CNV" in analysis_sections:
        cnvs = []
        if use_api_variants:
            try:
                cnv_payload = get_web_api_client().get_dna_cnvs(
                    sample_id=sample_id,
                    headers=build_forward_headers(request.headers),
                )
                cnvs = cnv_payload.cnvs
                app.logger.info("Loaded DNA CNV list from API service for sample %s", sample_id)
            except ApiRequestError as exc:
                app.logger.warning("DNA CNV API fetch failed for sample %s: %s", sample_id, exc)
                if app.config.get("WEB_API_STRICT_MODE", False):
                    return Response(str(exc), status=exc.status_code or 502)
        if not cnvs:
            cnv_query = build_cnv_query(
                str(sample["_id"]),
                filters={**sample_filters, "filter_genes": filter_genes},
            )
            cnvs = store.cnv_handler.get_sample_cnvs(cnv_query)
            if filter_cnveffects:
                cnvs = cnvtype_variant(cnvs, filter_cnveffects)
            cnvs = cnv_organizegenes(cnvs)
            app.logger.info("Loaded DNA CNV list from Mongo for sample %s", sample_id)

        display_sections_data["cnvs"] = deepcopy(cnvs)
        summary_sections_data["cnvs"] = [cnv for cnv in cnvs if cnv.get("interesting")]

    if "BIOMARKER" in analysis_sections:
        display_sections_data["biomarkers"] = list(
            store.biomarker_handler.get_sample_biomarkers(sample_id=str(sample["_id"]))
        )
        summary_sections_data["biomarkers"] = display_sections_data["biomarkers"]

    if "TRANSLOCATION" in analysis_sections:
        translocs = []
        if use_api_variants:
            try:
                transloc_payload = get_web_api_client().get_dna_translocations(
                    sample_id=sample_id,
                    headers=build_forward_headers(request.headers),
                )
                translocs = transloc_payload.translocations
                app.logger.info("Loaded DNA translocation list from API service for sample %s", sample_id)
            except ApiRequestError as exc:
                app.logger.warning("DNA translocation API fetch failed for sample %s: %s", sample_id, exc)
                if app.config.get("WEB_API_STRICT_MODE", False):
                    return Response(str(exc), status=exc.status_code or 502)
        if not translocs:
            translocs = store.transloc_handler.get_sample_translocations(sample_id=str(sample["_id"]))
            app.logger.info("Loaded DNA translocation list from Mongo for sample %s", sample_id)

        display_sections_data["translocs"] = translocs

    if "FUSION" in analysis_sections:
        display_sections_data["fusions"] = []
        summary_sections_data["translocs"] = [
            transloc for transloc in display_sections_data.get("translocs", []) if transloc.get("interesting")
        ]

    #################################################

    # this is to allow old samples to view plots, cnv + cnvprofile clash. Old assays used cnv as the entry for the plot, newer assays use cnv for path to cnv-file that was loaded.
    if "cnv" in sample:
        if sample["cnv"].lower().endswith((".png", ".jpg", ".jpeg")):
            sample["cnvprofile"] = sample["cnv"]

    # Get bams
    bam_id = store.bam_service_handler.get_bams(sample_ids)

    # Get Vep Meta data
    vep_variant_class_meta = store.vep_meta_handler.get_variant_class_translations(
        sample.get("vep", 103)
    )
    vep_conseq_meta = store.vep_meta_handler.get_conseq_translations(sample.get("vep", 103))

    # Oncokb information
    oncokb_genes = []
    for variant in variants:
        oncokb_gene = store.oncokb_handler.get_oncokb_action_gene(
            variant["INFO"]["selected_CSQ"]["SYMBOL"]
        )
        if oncokb_gene and "Hugo Symbol" in oncokb_gene:
            name = oncokb_gene["Hugo Symbol"]
            if name not in oncokb_genes:
                oncokb_genes.append(name)

    app.logger.info(f"oncokb_selected_genes : {oncokb_genes} ")

    ######## TODO: AI TEXT ##############
    ## "AI"-text depending on what analysis has been done. Add translocs and cnvs if marked as interesting (HRD and MSI?)
    ## SNVs, non-optional. Though only has rules for PARP + myeloid and solid
    ai_text = ""
    conclusion = ""
    ai_text = generate_summary_text(
        sample_ids,
        assay_config,
        assay_panel_doc,
        summary_sections_data,
        filter_genes,
        checked_genelists,
    )

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
@require_sample_access("sample_id")
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
    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result
    DNAWorkflowService.validate_report_inputs(app.logger, sample, assay_config)
    base_dir = assay_config.get("reporting", {}).get("plots_path", None)

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
@require_sample_access("sample_id")
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
    use_api_variants = bool(app.config.get("WEB_API_READ_DNA_VARIANTS", False)) and request.method == "GET"
    if use_api_variants:
        try:
            payload = get_web_api_client().get_dna_variant(
                sample_id=sample_id,
                var_id=var_id,
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
            app.logger.warning("DNA variant detail API fetch failed for sample %s: %s", sample_id, exc)
            if app.config.get("WEB_API_STRICT_MODE", False):
                return Response(str(exc), status=exc.status_code or 502)

    variant = store.variant_handler.get_variant(var_id)
    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result
    assay_group: str = assay_config.get("asp_group", "unknown")
    subpanel: str | None = sample.get("subpanel")
    assay_group_mappings = store.asp_handler.get_asp_group_mappings()
    in_other = store.variant_handler.get_variant_in_other_samples(variant)
    has_hidden_comments = store.variant_handler.hidden_var_comments(var_id)
    expression = store.expression_handler.get_expression_data(list(variant.get("transcripts")))
    variant = store.blacklist_handler.add_blacklist_data([variant], assay_group)[0]
    variant_desc = "NOTHING_IN_HERE"
    if (
        variant["INFO"]["selected_CSQ"]["SYMBOL"] == "CALR"
        and variant["INFO"]["selected_CSQ"]["EXON"] == "9/9"
        and "frameshift_variant" in variant["INFO"]["selected_CSQ"]["Consequence"]
    ):
        variant_desc = "EXON 9 FRAMESHIFT"
    if (
        variant["INFO"]["selected_CSQ"]["SYMBOL"] == "FLT3"
        and "SVLEN" in variant["INFO"]
        and variant["INFO"]["SVLEN"] > 10
    ):
        variant_desc = "ITD"
    civic = store.civic_handler.get_civic_data(variant, variant_desc)
    civic_gene = store.civic_handler.get_civic_gene_info(variant["INFO"]["selected_CSQ"]["SYMBOL"])
    oncokb_hgvsp = []
    if len(variant["INFO"]["selected_CSQ"]["HGVSp"]) > 0:
        hgvsp = dna_template_filters.one_letter_p(variant["INFO"]["selected_CSQ"]["HGVSp"])
        hgvsp = hgvsp.replace("p.", "")
        oncokb_hgvsp.append(hgvsp)
    if variant["INFO"]["selected_CSQ"]["Consequence"] in [
        "frameshift_variant",
        "stop_gained",
        "frameshift_deletion",
        "frameshift_insertion",
    ]:
        oncokb_hgvsp.append("Truncating Mutations")
    oncokb = store.oncokb_handler.get_oncokb_anno(variant, oncokb_hgvsp)
    oncokb_action = store.oncokb_handler.get_oncokb_action(variant, oncokb_hgvsp)
    oncokb_gene = store.oncokb_handler.get_oncokb_gene(variant["INFO"]["selected_CSQ"]["SYMBOL"])
    brca_exchange = store.brca_handler.get_brca_data(variant, assay_group)
    iarc_tp53 = store.iarc_tp53_handler.find_iarc_tp53(variant)
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    if not sample_ids:
        sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)
    pon = format_pon(variant)
    (
        annotations,
        latest_classification,
        other_classifications,
        annotations_interesting,
    ) = store.annotation_handler.get_global_annotations(variant, assay_group, subpanel)
    if not latest_classification or latest_classification.get("class") == 999:
        variant = add_alt_class(variant, assay_group, subpanel)
    else:
        variant["additional_classifications"] = None
    vep_variant_class_meta = store.vep_meta_handler.get_variant_class_translations(sample.get("vep", 103))
    vep_conseq_meta = store.vep_meta_handler.get_conseq_translations(sample.get("vep", 103))
    app.logger.info("Loaded DNA variant detail from Mongo for sample %s", sample_id)
    return render_template(
        "show_variant_vep.html",
        variant=variant,
        in_other=in_other,
        annotations=annotations,
        hidden_comments=has_hidden_comments,
        latest_classification=latest_classification,
        expression=expression,
        civic=civic,
        civic_gene=civic_gene,
        oncokb=oncokb,
        oncokb_action=oncokb_action,
        oncokb_gene=oncokb_gene,
        sample=sample,
        brca_exchange=brca_exchange,
        iarc_tp53=iarc_tp53,
        assay_group=assay_group,
        pon=pon,
        other_classifications=other_classifications,
        subpanel=subpanel,
        sample_ids=sample_ids,
        bam_id=bam_id,
        annotations_interesting=annotations_interesting,
        vep_var_class_translations=vep_variant_class_meta,
        vep_conseq_translations=vep_conseq_meta,
        assay_group_mappings=assay_group_mappings,
    )
