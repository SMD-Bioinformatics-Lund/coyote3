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
from coyote.blueprints.dna import dna_bp, filters
from coyote.blueprints.dna.varqueries import build_query
from coyote.blueprints.dna.cnvqueries import build_cnv_query
from coyote.blueprints.dna.forms import DNAFilterForm, create_assay_group_form
from coyote.errors.exceptions import AppError
from datetime import datetime
from bson import ObjectId
from collections import defaultdict
from coyote.util.decorators.access import require_sample_access
from coyote.util.misc import get_sample_and_assay_config
from coyote.services.auth.decorators import require
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

    # sample = store.sample_handler.get_sample(sample_id)  # sample_id = name/id
    sample_has_filters = sample.get("filters", None)

    # Get case and control samples
    # TODO: Should be available in the sample doc instead of processing the sample again
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    if not sample_ids:
        sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))

    ## get the assay from the sample, fallback to the first group if not set
    # TODO: This should be set in the sample doc and get it by the assay key in the sample and not by the group
    sample_assay = sample.get("assay")

    # Get the profile from the sample, fallback to production if not set
    # TODO: This should be set in the sample doc and get it by the profile key in the sample
    sample_profile = sample.get("profile", "production")

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get(
        "asp_group", "unknown"
    )  # myeloid, solid, lymphoid
    subpanel: str | None = sample.get("subpanel")  # breast, LP, lung, etc.
    analysis_sections = assay_config.get("analysis_types", [])
    display_sections_data = {}
    summary_sections_data = {}
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    # Get the entire genelist for the sample panel
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)

    # Get the genelists for the sample panel
    insilico_panel_genelists = store.isgl_handler.get_isgl_by_asp(
        sample_assay, is_active=True
    )
    all_panel_genelist_names = util.common.get_assay_genelist_names(
        insilico_panel_genelists
    )

    # Adding the default gene lists to the assay_config, if the use_diagnosis_genelist is set to true
    if assay_config.get("use_diagnosis_genelist", False) and subpanel:
        assay_default_config_genelist_ids = store.isgl_handler.get_isgl_ids(
            sample_assay, subpanel, "genelist", is_active=True
        )
        assay_config["filters"]["genelists"].extend(
            assay_default_config_genelist_ids
        )

    # Get filter settings from the sample and merge with assay config if sample does not have values
    sample = util.common.merge_sample_settings_with_assay_config(
        sample, assay_config
    )
    sample_filters = deepcopy(sample.get("filters", {}))

    # Update the sample filters with the default values from the assay config if the sample is new and does not have any filters set
    if not sample_has_filters:
        store.sample_handler.reset_sample_settings(
            sample["_id"], assay_config.get("filters")
        )

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
            app.logger.info(
                f"Resetting filters to default settings for the sample {sample_id}"
            )
            store.sample_handler.reset_sample_settings(
                _id, assay_config.get("filters", {})
            )
        else:
            filters_from_form = util.common.format_filters_from_form(
                form, assay_config_schema
            )
            store.sample_handler.update_sample_filters(_id, filters_from_form)

        ## get sample again to receive updated forms!
        sample = store.sample_handler.get_sample_by_id(_id)
        sample_filters = deepcopy(sample.get("filters"))

    ############################################################################

    # Check if the sample has hidden comments
    has_hidden_comments = store.sample_handler.hidden_sample_comments(
        sample.get("_id")
    )

    # sample filters, either set, or default
    cnv_effects = sample_filters.get("cnveffects", [])
    checked_genelists = sample_filters.get("genelists", [])

    # Get the genelists for the sample panel checked genelists from the filters
    checked_genelists_genes_dict: list[dict] = (
        store.isgl_handler.get_isgl_by_ids(checked_genelists)
    )
    genes_covered_in_panel: list[dict] = (
        util.common.get_genes_covered_in_panel(
            checked_genelists_genes_dict, assay_panel_doc
        )
    )

    # TODO: We can get the list of germline genes for the panel or selected genelists

    filter_conseq = util.dna.get_filter_conseq_terms(
        sample_filters.get("vep_consequences", [])
    )

    # Create a unique list of genes from the selected genelists which are currently active in the panel
    filter_genes = util.common.create_filter_genelist(genes_covered_in_panel)
    filter_cnveffects = util.dna.create_cnveffectlist(cnv_effects)

    # Add them to the form and update with the requested settings
    form_data = deepcopy(sample_filters)
    form_data.update(
        {
            **{
                f"vep_{k}": True
                for k in sample_filters.get("vep_consequences", [])
            },
            **{
                f"cnveffect_{k}": True
                for k in sample_filters.get("cnveffects", [])
            },
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
    variants = store.blacklist_handler.add_blacklist_data(
        variants, assay_group
    )

    # Add global annotations for the variants
    variants, tiered_variants = util.dna.add_global_annotations(
        variants, assay_group, subpanel
    )
    summary_sections_data["snvs"] = tiered_variants

    # Add hotspot data
    variants = util.dna.hotspot_variant(variants)

    display_sections_data["snvs"] = deepcopy(variants)

    ### SNV FILTRATION ENDS HERE ###

    ## GET Other sections CNVs TRANSLOCS and OTHER BIOMARKERS ##
    if "CNV" in analysis_sections:
        cnv_query = build_cnv_query(
            str(sample["_id"]),
            filters={**sample_filters, "filter_genes": filter_genes},
        )
        cnvs = store.cnv_handler.get_sample_cnvs(cnv_query)
        if filter_cnveffects:
            cnvs = util.dna.cnvtype_variant(cnvs, filter_cnveffects)
        cnvs = util.dna.cnv_organizegenes(cnvs)

        display_sections_data["cnvs"] = deepcopy(cnvs)
        summary_sections_data["cnvs"] = list(
            store.cnv_handler.get_interesting_sample_cnvs(
                sample_id=str(sample["_id"])
            )
        )

    if "BIOMARKER" in analysis_sections:
        display_sections_data["biomarkers"] = list(
            store.biomarker_handler.get_sample_biomarkers(
                sample_id=str(sample["_id"])
            )
        )
        summary_sections_data["biomarkers"] = display_sections_data[
            "biomarkers"
        ]

    if "TRANSLOCATION" in analysis_sections:
        display_sections_data["translocs"] = (
            store.transloc_handler.get_sample_translocations(
                sample_id=str(sample["_id"])
            )
        )

    if "FUSION" in analysis_sections:
        display_sections_data["fusions"] = []
        summary_sections_data["translocs"] = (
            store.transloc_handler.get_interesting_sample_translocations(
                sample_id=str(sample["_id"])
            )
        )

    #################################################

    # this is to allow old samples to view plots, cnv + cnvprofile clash. Old assays used cnv as the entry for the plot, newer assays use cnv for path to cnv-file that was loaded.
    if "cnv" in sample:
        if sample["cnv"].lower().endswith((".png", ".jpg", ".jpeg")):
            sample["cnvprofile"] = sample["cnv"]

    # Get bams
    bam_id = store.bam_service_handler.get_bams(sample_ids)

    # Get Vep Meta data
    vep_variant_class_meta = (
        store.vep_meta_handler.get_variant_class_translations(
            sample.get("vep", 103)
        )
    )
    vep_conseq_meta = store.vep_meta_handler.get_conseq_translations(
        sample.get("vep", 103)
    )

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
    ai_text = util.bpcommon.generate_summary_text(
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


# TODO
@dna_bp.route("/<sample_id>/multi_class", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_snvs", min_role="user", min_level=9)
def classify_multi_variant(sample_id: str) -> Response:
    """
    Classifies multiple variants for a given sample.

    This endpoint processes a POST request to classify several variants at once.
    It retrieves the action to perform, the list of selected variant object IDs, and optional classification parameters
    such as assay group, subpanel, and tier from the form data. The function then applies the requested classification
    action to the selected variants.

    Args:
        sample_id (str): The unique identifier of the sample whose variants are to be classified.

    Returns:
        flask.Response: A redirect or response indicating the result of the classification operation.
    """
    action = request.form.get("action")
    variants_to_modify = request.form.getlist("selected_object_id")
    assay_group = request.form.get("assay_group")
    subpanel = request.form.get("subpanel")
    tier = request.form.get("tier")
    irrelevant = request.form.get("irrelevant")
    false_positive = request.form.get("false_positive")

    if tier and action == "apply":
        bulk_docs = []
        for variant_id in variants_to_modify:
            var = store.variant_handler.get_variant(str(variant_id))
            if not var:
                continue

            selected_csq = var.get("INFO", {}).get("selected_CSQ", {})
            transcript = selected_csq.get("Feature")
            gene = selected_csq.get("SYMBOL")
            hgvs_p = selected_csq.get("HGVSp")
            hgvs_c = selected_csq.get("HGVSc")
            hgvs_g = f"{var['CHROM']}:{var['POS']}:{var['REF']}/{var['ALT']}"
            consequence = selected_csq.get("Consequence")
            gene_oncokb = store.oncokb_handler.get_oncokb_gene(gene)

            text = util.bpcommon.create_annotation_text_from_gene(
                gene, consequence, assay_group, gene_oncokb=gene_oncokb
            )

            nomenclature = "p"
            if hgvs_p != "" and hgvs_p is not None:
                variant = hgvs_p
            elif hgvs_c != "" and hgvs_c is not None:
                variant = hgvs_c
                nomenclature = "c"
            else:
                variant = hgvs_g
                nomenclature = "g"

            variant_data = {
                "gene": gene,
                "assay_group": assay_group,
                "subpanel": subpanel,
                "transcript": transcript,
            }

            class_doc = util.common.create_classified_variant_doc(
                variant=variant,
                nomenclature=nomenclature,
                class_num=3,
                variant_data=variant_data,
            )

            bulk_docs.append(deepcopy(class_doc))

            # Add the annotation text to the database
            text_doc = util.common.create_classified_variant_doc(
                variant=variant,
                nomenclature=nomenclature,
                class_num=3,
                variant_data=variant_data,
                text=text,
            )
            bulk_docs.append(deepcopy(text_doc))

        if bulk_docs:
            store.annotation_handler.insert_annotation_bulk(bulk_docs)

    if false_positive:
        if action == "apply":
            store.variant_handler.mark_false_positive_var_bulk(
                variants_to_modify
            )
        elif action == "remove":
            store.variant_handler.unmark_false_positive_var_bulk(
                variants_to_modify
            )
    if irrelevant:
        if action == "apply":
            store.variant_handler.mark_irrelevant_var_bulk(variants_to_modify)
        elif action == "remove":
            store.variant_handler.unmark_irrelevant_var_bulk(
                variants_to_modify
            )
    return redirect(url_for("dna_bp.list_variants", sample_id=sample_id))


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
    variant = store.variant_handler.get_variant(var_id)
    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get(
        "asp_group", "unknown"
    )  # myeloid, solid, lymphoid
    subpanel: str | None = sample.get("subpanel")  # breast, LP, lung, etc.

    # Get assay groups mappings with the sample assay
    assay_group_mappings = store.asp_handler.get_asp_group_mappings()
    # Get sample data if the variant is present in other samples
    in_other = store.variant_handler.get_variant_in_other_samples(variant)

    # Check if variant has hidden comments
    has_hidden_comments = store.variant_handler.hidden_var_comments(var_id)

    # TODO: We have to find a way to present this data
    expression = store.expression_handler.get_expression_data(
        list(variant.get("transcripts"))
    )

    variant = store.blacklist_handler.add_blacklist_data(
        [variant], assay_group
    )[0]

    # Find civic data
    variant_desc = "NOTHING_IN_HERE"
    if (
        variant["INFO"]["selected_CSQ"]["SYMBOL"] == "CALR"
        and variant["INFO"]["selected_CSQ"]["EXON"] == "9/9"
        and "frameshift_variant"
        in variant["INFO"]["selected_CSQ"]["Consequence"]
    ):
        variant_desc = "EXON 9 FRAMESHIFT"
    if (
        variant["INFO"]["selected_CSQ"]["SYMBOL"] == "FLT3"
        and "SVLEN" in variant["INFO"]
        and variant["INFO"]["SVLEN"] > 10
    ):
        variant_desc = "ITD"

    civic = store.civic_handler.get_civic_data(variant, variant_desc)

    civic_gene = store.civic_handler.get_civic_gene_info(
        variant["INFO"]["selected_CSQ"]["SYMBOL"]
    )

    # Find OncoKB data
    oncokb_hgvsp = []
    if len(variant["INFO"]["selected_CSQ"]["HGVSp"]) > 0:
        hgvsp = filters.one_letter_p(variant["INFO"]["selected_CSQ"]["HGVSp"])
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
    oncokb_action = store.oncokb_handler.get_oncokb_action(
        variant, oncokb_hgvsp
    )
    oncokb_gene = store.oncokb_handler.get_oncokb_gene(
        variant["INFO"]["selected_CSQ"]["SYMBOL"]
    )

    # Find BRCA-exchange data
    brca_exchange = store.brca_handler.get_brca_data(variant, assay_group)

    # Find IARC TP53 data
    iarc_tp53 = store.iarc_tp53_handler.find_iarc_tp53(variant)

    # Get bams
    # TODO: This should be set in the sample doc and get it by the sample ids in the sample
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    if not sample_ids:
        # If no case and control samples found, get sample ids from the variant
        # This is a fallback for older samples that do not have case/control samples set
        sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)

    # Format PON (panel of normals) data
    pon = util.dna.format_pon(variant)

    # Get global annotations for the variant
    (
        annotations,
        latest_classification,
        other_classifications,
        annotations_interesting,
    ) = store.annotation_handler.get_global_annotations(
        variant, assay_group, subpanel
    )

    if not latest_classification or latest_classification.get("class") == 999:
        variant = util.dna.add_alt_class(variant, assay_group, subpanel)
    else:
        variant["additional_classifications"] = None

    # Get Vep Meta data
    vep_variant_class_meta = (
        store.vep_meta_handler.get_variant_class_translations(
            sample.get("vep", 103)
        )
    )
    vep_conseq_meta = store.vep_meta_handler.get_conseq_translations(
        sample.get("vep", 103)
    )

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


@dna_bp.route("/gene_simple/<string:gene_name>", methods=["GET", "POST"])
@require("view_gene_annotations", min_role="user", min_level=9)
def gene_view_simple(gene_name: str) -> Response | str:
    """
    Display a simple gene annotation view.

    This view renders a form for selecting assay groups and displays processed gene annotations
    for the specified gene. If the form is submitted, it collects the checked assays.

    Args:
        gene_name (str): The name of the gene to display annotations for.

    Returns:
        flask.Response | str: Rendered HTML template for the gene view, or a redirect/response
        if required data is missing.
    """
    AssayGroupForm = create_assay_group_form()
    form = AssayGroupForm()

    annotations = store.annotation_handler.get_gene_annotations(gene_name)
    annotations_dict = util.bpcommon.process_gene_annotations(annotations)

    checked_assays = []
    if form.validate_on_submit():
        checked_assays = [
            k for k, v in form.data.items() if v and k not in ["csrf_token"]
        ]

    return render_template(
        "gene_view2.html",
        form=form,
        checked_assays=checked_assays,
        gene=gene_name,
        annotations=annotations,
        annodict=annotations_dict,
    )


@dna_bp.route("/gene/<string:gene_name>", methods=["GET", "POST"])
@require("view_gene_annotations", min_role="user", min_level=9)
def gene_view(gene_name: str) -> Response | str:
    """
    Display detailed gene-specific variant information.

    This view retrieves and displays all variants associated with a given gene.
    It fetches variants from the database, adds global annotations, and prepares
    a summary for rendering in the gene-specific variant template.

    Args:
        gene_name (str): The name of the gene for which to display variant information.

    Returns:
        flask.Response | str: Rendered HTML template showing gene-specific variants,
        or a redirect/response if required data is missing.

    Side Effects:
        - Logs the number of gene-specific variants.
        - May perform slow operations when adding global annotations.
    """
    variants_iter = store.variant_handler.get_variants_by_gene(gene_name)
    variants = list(variants_iter)

    app.logger.debug(f"gene specific variants: {len(variants)}")

    # TODO:  How slow is this????
    variants, tiered_variants = util.dna.add_global_annotations(
        variants, "assay", "subpanel"
    )

    variant_summary = defaultdict(dict)
    sample_oids = []
    for var in variants:
        short_pos = var.get("simple_id", None)

        if not var.get("classification"):
            continue

        if var["classification"].get("class", 999) != 999:

            sample_oids.append(ObjectId(var["SAMPLE_ID"]))

            if short_pos in variant_summary:
                variant_summary[short_pos]["count"] += 1
                variant_summary[short_pos]["samples"].append(var["SAMPLE_ID"])
            else:
                variant_summary[short_pos]["count"] = 1
                variant_summary[short_pos]["CSQ"] = var["INFO"]["selected_CSQ"]
                variant_summary[short_pos]["anno"] = var["global_annotations"]
                variant_summary[short_pos]["class"] = var["classification"]
                variant_summary[short_pos]["samples"] = [var["SAMPLE_ID"]]

    # Get display names for the samples, from db.
    samples = store.sample_handler.get_samples_by_oids(sample_oids)

    # Create hash for translation ID -> display name, from samples
    sample_names = {}
    for sample in samples:
        sample_names[str(sample["_id"])] = sample["name"]

    return render_template(
        "gene_view.html", variants=variant_summary, sample_names=sample_names
    )


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/unfp", methods=["POST"])
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def unmark_false_variant(sample_id: str, var_id: str) -> Response:
    """
    Unmark the False Positive status of a variant in the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: Redirects to the variant detail view after unmarking the variant as false positive.
    """
    store.variant_handler.unmark_false_positive_var(var_id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route("/<string:sample_id>/var/<string:var_id>/fp", methods=["POST"])
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def mark_false_variant(sample_id: str, var_id: str) -> Response:
    """
    Mark a variant as False Positive in the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: Redirects to the variant detail view after marking the variant as false positive.
    """
    store.variant_handler.mark_false_positive_var(var_id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/uninterest", methods=["POST"]
)
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def unmark_interesting_variant(sample_id: str, var_id: str) -> Response:
    """
    Removes the `interesting` status from a variant in the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: Redirects to the variant detail view after unmarking the variant as interesting.
    """
    store.variant_handler.unmark_interesting_var(var_id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/interest", methods=["POST"]
)
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def mark_interesting_variant(sample_id: str, var_id: str) -> Response:
    """
    Mark the `interesting` status of a variant in the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: Redirects to the variant detail view after marking the variant as interesting.
    """
    store.variant_handler.mark_interesting_var(var_id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/relevant", methods=["POST"]
)
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def unmark_irrelevant_variant(sample_id: str, var_id: str) -> Response:
    """
    Unmark the irrelevant status of a variant in the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: Redirects to the variant detail view after unmarking the variant as irrelevant.
    """
    store.variant_handler.unmark_irrelevant_var(var_id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/irrelevant", methods=["POST"]
)
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def mark_irrelevant_variant(sample_id: str, var_id: str) -> Response:
    """
    Mark irrelevant status of a variant in the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: Redirects to the variant detail view after marking the variant as irrelevant.
    """
    store.variant_handler.mark_irrelevant_var(var_id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/blacklist", methods=["POST"]
)
@require("manage_snvs", min_role="admin")
@require_sample_access("sample_id")
def add_variant_to_blacklist(sample_id: str, var_id: str) -> Response:
    """
    Add a variant to the blacklist for a given sample.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: Redirects to the variant detail view after blacklisting the variant.
    """
    var = store.variant_handler.get_variant(var_id)
    sample = store.sample_handler.get_sample_by_id(var["SAMPLE_ID"])
    assay = util.common.get_assay_from_sample(sample)
    store.blacklist_handler.blacklist_variant(var, assay)
    return redirect(url_for("dna_bp.show_variant", sample_id=sample_id, id=id))


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/classify", methods=["POST"]
)
@require(permission="assign_tier", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def classify_variant(sample_id: str, var_id: str) -> Response:
    """
    Classify a DNA variant based on the provided form data.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: The response after classifying the variant.
    """
    form_data = request.form.to_dict()
    class_num = util.common.get_tier_classification(form_data)
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    if class_num != 0:
        store.annotation_handler.insert_classified_variant(
            variant, nomenclature, class_num, form_data
        )

    if class_num != 0:
        if nomenclature == "f":
            return redirect(url_for("rna_bp.show_fusion", id=var_id))

    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/rmclassify", methods=["POST"]
)
@require(permission="remove_tier", min_role="admin")
@require_sample_access("sample_id")
def remove_classified_variant(sample_id: str, var_id: str) -> Response:
    """
    Remove a classified variant from the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: Redirects to the variant detail view after removing the classified variant.
    """
    form_data = request.form.to_dict()
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", id=var_id))
    delete_result = store.annotation_handler.delete_classified_variant(
        variant, nomenclature, form_data
    )
    app.logger.debug(delete_result)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


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
@require("add_variant_comment", min_role="user", min_level=9)
@require_sample_access("sample_id")
def add_var_comment(
    sample_id: str, id: str = None, **kwargs
) -> Response | str:
    """
    Add a comment to a variant.

    Args:
        sample_id (str): The unique identifier of the sample.
        id (str, optional): The identifier of the variant, CNV, fusion, or translocation. Defaults to None.
        **kwargs: Additional keyword arguments.

    Returns:
        Response | str: A redirect or rendered template after adding the comment.
    """
    id = (
        id
        or request.view_args.get("var_id")
        or request.view_args.get("cnv_id")
        or request.view_args.get("fus_id")
        or request.view_args.get("transloc_id")
    )

    # If global checkbox. Save variant with the protein, coding och genomic nomenclature in decreasing priority
    form_data = request.form.to_dict()
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    doc = util.bpcommon.create_comment_doc(
        form_data, nomenclature=nomenclature, variant=variant
    )
    _type = form_data.get("global", None)
    if _type == "global":
        store.annotation_handler.add_anno_comment(doc)
        flash("Global comment added", "green")

    if nomenclature == "f":
        if _type != "global":
            store.fusion_handler.add_fusion_comment(id, doc)
        return redirect(
            url_for("rna_bp.show_fusion", sample_id=sample_id, id=id)
        )
    elif nomenclature == "t":
        if _type != "global":
            store.transloc_handler.add_transloc_comment(id, doc)
        return redirect(
            url_for(
                "dna_bp.show_transloc", sample_id=sample_id, transloc_id=id
            )
        )
    elif nomenclature == "cn":
        if _type != "global":
            store.cnv_handler.add_cnv_comment(id, doc)
        return redirect(
            url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=id)
        )
    else:
        if _type != "global":
            store.variant_handler.add_var_comment(id, doc)

    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/hide_variant_comment",
    methods=["POST"],
)
@require("hide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def hide_variant_comment(sample_id: str, var_id: str) -> Response:
    """
    Hide a comment for a specific variant.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: Redirects to the variant detail view after hiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.variant_handler.hide_var_comment(var_id, comment_id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


@dna_bp.route(
    "/<string:sample_id>/var/<string:var_id>/unhide_variant_comment",
    methods=["POST"],
)
@require("unhide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def unhide_variant_comment(sample_id, var_id):
    """
    Unhide a previously hidden comment for a specific variant.

    Args:
        sample_id (str): The unique identifier of the sample.
        var_id (str): The unique identifier of the variant.

    Returns:
        flask.Response: Redirects to the variant detail view after unhiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.variant_handler.unhide_variant_comment(var_id, comment_id)
    return redirect(
        url_for("dna_bp.show_variant", sample_id=sample_id, var_id=var_id)
    )


###### CNVS VIEW PAGE #######
@dna_bp.route("/<string:sample_id>/cnv/<string:cnv_id>")
@require_sample_access("sample_id")
def show_cnv(sample_id: str, cnv_id: str) -> Response | str:
    """
    Show CNVs view page.

    Args:
        sample_id (str): The unique identifier of the sample.
        cnv_id (str): The unique identifier of the CNV.

    Returns:
        Response | str: Rendered HTML template for the CNV view or a redirect/response if not found.
    """
    cnv = store.cnv_handler.get_cnv(cnv_id)
    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get(
        "asp_group", "unknown"
    )  # myeloid, solid, lymphoid

    # TODO: This should be set in the sample doc and get it by the sample ids in the sample
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    if not sample_ids:
        # If no case and control samples found, get sample ids from the variant
        # This is a fallback for older samples that do not have case/control samples set
        sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)
    hidden_cnv_comments = store.cnv_handler.hidden_cnv_comments(cnv_id)

    annotations = store.cnv_handler.get_cnv_annotations(cnv)
    return render_template(
        "show_cnvwgs.html",
        cnv=cnv,
        sample=sample,
        assay_group=assay_group,
        classification=999,
        annotations=annotations,
        sample_ids=sample_ids,
        bam_id=bam_id,
        hidden_comments=hidden_cnv_comments,
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/unmarkinterestingcnv",
    methods=["POST"],
)
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def unmark_interesting_cnv(sample_id: str, cnv_id: str) -> Response:
    """
    Unmark CNV as interesting.

    Args:
        sample_id (str): The unique identifier of the sample.
        cnv_id (str): The unique identifier of the CNV.

    Returns:
        flask.Response: Redirects to the CNV view after unmarking as interesting.
    """
    store.cnv_handler.unmark_interesting_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/interestingcnv", methods=["POST"]
)
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def mark_interesting_cnv(sample_id: str, cnv_id: str) -> Response:
    """
    Mark CNV as interesting.

    Args:
        sample_id (str): The unique identifier of the sample.
        cnv_id (str): The unique identifier of the CNV.

    Returns:
        flask.Response: Redirects to the CNV view after marking as interesting.
    """
    store.cnv_handler.mark_interesting_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route("<string:sample_id>/cnv/<string:cnv_id>/fpcnv", methods=["POST"])
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def mark_false_cnv(sample_id: str, cnv_id: str) -> Response:
    """
    Mark CNV as false positive.

    Args:
        sample_id (str): The unique identifier of the sample.
        cnv_id (str): The unique identifier of the CNV.

    Returns:
        flask.Response: Redirects to the CNV view after marking as false positive.
    """
    store.cnv_handler.mark_false_positive_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "/<string:sample_id>/cnv/<string:cnv_id>/unfpcnv", methods=["POST"]
)
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def unmark_false_cnv(sample_id: str, cnv_id: str) -> Response:
    """
    Unmark CNV as false positive.

    Args:
        sample_id (str): The unique identifier of the sample.
        cnv_id (str): The unique identifier of the CNV.

    Returns:
        flask.Response: Redirects to the CNV view after unmarking as false positive.
    """
    store.cnv_handler.unmark_false_positive_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/noteworthycnv", methods=["POST"]
)
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def mark_noteworthy_cnv(sample_id: str, cnv_id: str) -> Response:
    """
    Mark CNV as note worthy.

    Args:
        sample_id (str): The unique identifier of the sample.
        cnv_id (str): The unique identifier of the CNV.

    Returns:
        flask.Response: Redirects to the CNV view after marking as note worthy.
    """
    store.cnv_handler.noteworthy_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/notnoteworthycnv", methods=["POST"]
)
@require_sample_access("sample_id")
@require("manage_cnvs", min_role="user", min_level=9)
def unmark_noteworthy_cnv(sample_id: str, cnv_id: str) -> Response:
    """
    Unmark CNV as note worthy.

    Args:
        sample_id (str): The unique identifier of the sample.
        cnv_id (str): The unique identifier of the CNV.

    Returns:
        flask.Response: Redirects to the CNV view after unmarking as note worthy.
    """
    store.cnv_handler.unnoteworthy_cnv(cnv_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/hide_cnv_comment", methods=["POST"]
)
@require("hide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def hide_cnv_comment(sample_id: str, cnv_id: str) -> Response:
    """
    Hide CNV comment.

    Args:
        sample_id (str): The unique identifier of the sample.
        cnv_id (str): The unique identifier of the CNV.

    Returns:
        Response: Redirects to the CNV view after hiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.cnv_handler.hide_cnvs_comment(cnv_id, comment_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


@dna_bp.route(
    "<string:sample_id>/cnv/<string:cnv_id>/unhide_cnv_comment",
    methods=["POST"],
)
@require("unhide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def unhide_cnv_comment(sample_id: str, cnv_id: str) -> Response:
    """
    Unhide a previously hidden comment for a specific CNV.

    Args:
        sample_id (str): The unique identifier of the sample.
        cnv_id (str): The unique identifier of the CNV.

    Returns:
        flask.Response: Redirects to the CNV view after unhiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.cnv_handler.unhide_cnvs_comment(cnv_id, comment_id)
    return redirect(
        url_for("dna_bp.show_cnv", sample_id=sample_id, cnv_id=cnv_id)
    )


###### TRANSLOCATIONS VIEW PAGE #######
@dna_bp.route("/<string:sample_id>/transloc/<string:transloc_id>")
@require_sample_access("sample_id")
def show_transloc(sample_id: str, transloc_id: str) -> Response | str:
    """
    Show Translocation view page.

    Args:
        sample_id (str): The unique identifier of the sample.
        transloc_id (str): The unique identifier of the translocation.

    Returns:
        Response | str: Rendered HTML template for the translocation view or a redirect/response if not found.
    """
    transloc = store.transloc_handler.get_transloc(transloc_id)

    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get(
        "asp_group", "unknown"
    )  # myeloid, solid, lymphoid

    # TODO: This should be set in the sample doc and get it by the sample ids in the sample
    sample_ids = util.common.get_case_and_control_sample_ids(sample)
    if not sample_ids:
        # If no case and control samples found, get sample ids from the variant
        # This is a fallback for older samples that do not have case/control samples set
        sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)
    hidden_transloc_comments = store.transloc_handler.hidden_transloc_comments(
        transloc_id
    )

    vep_conseq_meta = store.vep_meta_handler.get_conseq_translations(
        sample.get("vep", 103)
    )

    annotations = store.transloc_handler.get_transloc_annotations(transloc)
    return render_template(
        "show_transloc.html",
        tl=transloc,
        sample=sample,
        assay_group=assay_group,
        classification=999,
        annotations=annotations,
        bam_id=bam_id,
        vep_conseq_translations=vep_conseq_meta,
        hidden_comments=hidden_transloc_comments,
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/interestingtransloc",
    methods=["POST"],
)
@require_sample_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def mark_interesting_transloc(sample_id: str, transloc_id: str) -> Response:
    """
    Mark a translocation as interesting.

    Args:
        sample_id (str): The unique identifier of the sample.
        transloc_id (str): The unique identifier of the translocation.

    Returns:
        flask.Response: Redirects to the translocation view after marking as interesting.
    """
    store.transloc_handler.mark_interesting_transloc(transloc_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/uninterestingtransloc",
    methods=["POST"],
)
@require_sample_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def unmark_interesting_transloc(sample_id: str, transloc_id: str) -> Response:
    """
    Unmark a translocation as interesting.

    Args:
        sample_id (str): The unique identifier of the sample.
        transloc_id (str): The unique identifier of the translocation.

    Returns:
        flask.Response: Redirects to the translocation view after unmarking as interesting.
    """
    store.transloc_handler.unmark_interesting_transloc(transloc_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/fptransloc",
    methods=["POST"],
)
@require_sample_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def mark_false_transloc(sample_id: str, transloc_id: str) -> Response:
    """
    Mark a translocation as false positive.

    Args:
        sample_id (str): The unique identifier of the sample.
        transloc_id (str): The unique identifier of the translocation.

    Returns:
        flask.Response: Redirects to the translocation view after marking as false positive.
    """
    store.transloc_handler.mark_false_positive_transloc(transloc_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/ptransloc",
    methods=["POST"],
)
@require_sample_access("sample_id")
@require("manage_translocs", min_role="user", min_level=9)
def unmark_false_transloc(sample_id: str, transloc_id: str) -> Response:
    """
    Unmark a translocation as false positive.

    Args:
        sample_id (str): The unique identifier of the sample.
        transloc_id (str): The unique identifier of the translocation.

    Returns:
        flask.Response: Redirects to the translocation view after unmarking as false positive.
    """
    store.transloc_handler.unmark_false_positive_transloc(transloc_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/hide_variant_comment",
    methods=["POST"],
)
@require("hide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def hide_transloc_comment(sample_id: str, transloc_id: str) -> Response:
    """
    Hide a comment for a specific translocation.

    Args:
        sample_id (str): The unique identifier of the sample.
        transloc_id (str): The unique identifier of the translocation.

    Returns:
        flask.Response: Redirects to the translocation view after hiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.transloc_handler.hide_transloc_comment(transloc_id, comment_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


@dna_bp.route(
    "/<string:sample_id>/transloc/<string:transloc_id>/unhide_variant_comment",
    methods=["POST"],
)
@require("unhide_variant_comment", min_role="manager", min_level=99)
@require_sample_access("sample_id")
def unhide_transloc_comment(sample_id: str, transloc_id: str) -> Response:
    """
    Unhide a previously hidden comment for a specific translocation.

    Args:
        sample_id (str): The unique identifier of the sample.
        transloc_id (str): The unique identifier of the translocation.

    Returns:
        flask.Response: Redirects to the translocation view after unhiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.transloc_handler.unhide_transloc_comment(transloc_id, comment_id)
    return redirect(
        url_for(
            "dna_bp.show_transloc",
            sample_id=sample_id,
            transloc_id=transloc_id,
        )
    )


##### PREVIEW REPORT ######
@dna_bp.route(
    "/sample/<string:sample_id>/preview_report", methods=["GET", "POST"]
)
@require_sample_access("sample_id")
@require("preview_report", min_role="user", min_level=9)
def generate_dna_report(sample_id: str, **kwargs) -> Response | str:
    """
    Generate and render a DNA report for a given sample.

    This function retrieves sample and assay configuration data, applies filters,
    gathers variant and biomarker information, and prepares all necessary data
    for rendering a comprehensive DNA report. The report includes SNVs, CNVs,
    biomarkers, translocations, fusions, and low coverage regions, depending on
    the assay configuration and available data.

    Args:
        sample_id (str): The identifier (name or ID) of the sample to generate the report for.
        **kwargs: Additional keyword arguments. Supported:
            save (int, optional): If set, indicates the report should be saved.

    Returns:
        Response | str: Rendered HTML template for the DNA report, or a redirect
        response if required data is missing.

    Side Effects:
        - Flashes messages to the user if sample or assay configuration is missing.
        - Redirects to the home screen if critical data is not found.
        - Logs debug information about the assay group and configuration.
    """

    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    ## get the assay from the sample, fallback to the first group if not set
    # TODO: This should be set in the sample doc and get it by the assay key in the sample and not by the group
    sample_assay = sample.get("assay", None)

    if sample_assay is None:
        flash("No assay group found for sample", "red")
        return redirect(url_for("home_bp.samples_home"))

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get("asp_group", "unknown")
    subpanel = sample.get("subpanel")
    report_sections = assay_config.get("reporting", {}).get(
        "report_sections", []
    )
    report_sections_data = {}
    app.logger.debug(
        f"Assay group: {assay_group} - DNA config: {pformat(report_sections)}"
    )
    app.logger.debug(f"Assay group: {assay_group} - Subpanel: {subpanel}")

    # Get number of the samples in this report (paired, unpaired)
    sample["num_samples"] = store.variant_handler.get_num_samples(
        str(sample["_id"])
    )

    # Get the entire genelist for the sample panel
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)

    # Get the genelists for the sample panel
    insilico_panel_genelists = store.isgl_handler.get_isgl_by_asp(
        sample_assay, is_active=True
    )
    all_panel_genelist_names = util.common.get_assay_genelist_names(
        insilico_panel_genelists
    )

    # sample filters
    if not sample.get("filters"):
        sample = util.common.merge_sample_settings_with_assay_config(
            sample, assay_config
        )

    sample_filters = deepcopy(sample.get("filters", {}))

    # Get the genelist filters from the sample settings
    checked_genelists = sample_filters.get("genelists", [])
    checked_genelists_genes_dict: list[dict] = (
        store.isgl_handler.get_isgl_by_ids(checked_genelists)
    )

    genes_covered_in_panel: list[dict] = (
        util.common.get_genes_covered_in_panel(
            checked_genelists_genes_dict, assay_panel_doc
        )
    )

    filter_conseq = util.dna.get_filter_conseq_terms(
        sample_filters.get("vep_consequences", [])
    )
    # Create a unique list of genes from the selected genelists which are currently active in the panel
    filter_genes = util.common.create_filter_genelist(genes_covered_in_panel)

    disp_pos = []
    if assay_config.get("verification_samples"):
        if sample["name"] in assay_config["verification_samples"]:
            disp_pos = assay_config["verification_samples"][sample["name"]]

    # Get all the variants for the report
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
            "fp": {"$ne": True},
            "irrelevant": {"$ne": True},
        },
    )

    variants_iter = store.variant_handler.get_case_variants(query)
    variants = list(variants_iter)

    # Add blacklist data
    variants = store.blacklist_handler.add_blacklist_data(
        variants, assay=assay_group
    )

    # Add global annotations for the variants
    variants, tiered_variants = util.dna.add_global_annotations(
        variants, assay_group, subpanel
    )

    # Add hotspot data
    variants = util.dna.hotspot_variant(variants)

    # Filter variants for report
    variants = util.dna.filter_variants_for_report(
        variants, filter_genes, assay_group
    )

    # Sample dict for the variant summary table in the report
    report_sections_data["snvs"] = util.dna.get_simple_variants_for_report(
        variants, assay_config
    )

    ## GET CNVs TRANSLOCS and OTHER BIOMARKERS ##
    if "CNV" in report_sections:
        report_sections_data["cnvs"] = list(
            store.cnv_handler.get_interesting_sample_cnvs(
                sample_id=str(sample["_id"])
            )
        )

    if "CNV_PROFILE" in report_sections:
        report_sections_data["cnv_profile_base64"] = util.common.get_plot(
            os.path.basename(sample.get("cnvprofile", "")), assay_config
        )

    if "BIOMARKER" in report_sections:
        report_sections_data["biomarkers"] = list(
            store.biomarker_handler.get_sample_biomarkers(
                sample_id=str(sample["_id"])
            )
        )

    if "TRANSLOCATION" in report_sections:
        report_sections_data["translocs"] = (
            store.transloc_handler.get_interesting_sample_translocations(
                sample_id=str(sample["_id"])
            )
        )

    if "FUSION" in report_sections:
        report_sections_data["fusions"] = []

    # report header and date
    assay_config["reporting"]["report_header"] = util.common.get_report_header(
        assay_group,
        sample,
        assay_config["reporting"].get("report_header", "Unknown"),
    )

    # Get Vep Meta data
    vep_variant_class_meta = (
        store.vep_meta_handler.get_variant_class_translations(
            sample.get("vep", 103)
        )
    )

    save = kwargs.get("save", 0)
    report_date = datetime.now().date()

    fernet = app.config["FERNET"]

    return render_template(
        "dna_report.html",
        assay_config=assay_config,
        report_sections=report_sections,
        report_sections_data=report_sections_data,
        sample=sample,
        translation=util.report.VARIANT_CLASS_TRANSLATION,
        vep_var_class_translations=vep_variant_class_meta,
        class_desc=util.report.TIER_DESC,
        class_desc_short=util.report.TIER_SHORT_DESC,
        report_date=report_date,
        save=save,
        sample_assay=sample_assay,
        genes_covered_in_panel=genes_covered_in_panel,
        encrypted_panel_doc=util.common.encrypt_json(assay_panel_doc, fernet),
        encrypted_genelists=util.common.encrypt_json(
            genes_covered_in_panel, fernet
        ),
        encrypted_sample_filters=util.common.encrypt_json(
            sample_filters, fernet
        ),
    )


@dna_bp.route("/sample/<string:sample_id>/report/save")
@require_sample_access("sample_id")
@require("create_report", min_role="admin")
def save_dna_report(sample_id: str) -> Response:
    """
    Saves a DNA report for the specified sample.

    This function retrieves a sample by its ID, determines the appropriate assay group,
    and generates a DNA report in HTML format. The report is saved to a file system path
    based on the assay group and sample information. If a report with the same name already
    exists, an error is raised. The function also updates the sample's report records and
    provides user feedback via flash messages.

    Args:
        sample_id (str): The unique identifier of the sample for which the DNA report is to be saved.

    Returns:
        Response: A redirect response to the home screen.

    Raises:
        AppError: If a report with the same name already exists or if saving the report fails.
    """
    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    assay_group: str = assay_config.get("asp_group", "unknown")
    report_num: int = sample.get("report_num", 0) + 1
    report_id: str = f"{sample_id}.{report_num}"
    report_path: str = os.path.join(
        app.config.get("REPORTS_BASE_PATH", "reports"),
        assay_config.get("reporting", {}).get("report_path", assay_group),
    )
    os.makedirs(report_path, exist_ok=True)
    report_file: str = os.path.join(report_path, f"{report_id}.html")

    if os.path.exists(report_file):
        flash("Report already exists.", "red")
        app.logger.warning(f"Report file already exists: {report_file}")
        raise AppError(
            status_code=409,
            message="Report already exists with the requested name.",
            details=f"File name: {os.path.basename(report_file)}",
        )

    try:
        html = generate_dna_report(sample_id=sample_id, save=1)

        if not util.common.write_report(html, report_file):
            raise AppError(
                status_code=500,
                message=f"Failed to save report {report_id}.html",
                details="Could not write the report to the file system.",
            )
        store.sample_handler.save_report(
            sample_id=sample_id,
            report_id=report_id,
            filepath=report_file,
        )
        flash(f"Report {report_id}.html has been successfully saved.", "green")
        app.logger.info(f"Report saved: {report_file}")
    except AppError as app_err:
        flash(app_err.message, "red")
        app.logger.error(
            f"AppError: {app_err.message} | Details: {app_err.details}"
        )
    except Exception as exc:
        flash("An unexpected error occurred while saving the report.", "red")
        app.logger.exception(f"Unexpected error: {exc}")

    return redirect(url_for("home_bp.samples_home"))
