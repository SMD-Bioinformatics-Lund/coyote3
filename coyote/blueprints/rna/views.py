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
    redirect,
    render_template,
    request,
    url_for,
    Response,
)
from flask_login import current_user, login_required

from coyote.blueprints.rna.forms import FusionFilter

from coyote.extensions import store, util
from coyote.blueprints.rna import rna_bp, filters
from datetime import datetime
from flask_weasyprint import HTML, render_pdf
from coyote.util.decorators.access import require_sample_access
from coyote.util.misc import get_sample_and_assay_config
from copy import deepcopy
from wtforms import BooleanField
from coyote.blueprints.rna.fusion_queries import build_fusion_query


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

    # Inherit RNAFilterForm, pass all genepanels from mongodb, set as boolean, NOW IT IS DYNAMIC!
    if all_panel_genelist_names:
        for gene_list in all_panel_genelist_names:
            setattr(FusionFilter, f"genelist_{gene_list}", BooleanField())

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
    # Check if sample has hidden comments
    has_hidden_comments = store.sample_handler.hidden_sample_comments(sample.get("_id"))

    fusion_effects = sample_filters.get("fusion_effects", [])
    fusion_callers = sample_filters.get("fusion_callers", [])

    checked_fusionlists = sample_filters.get("fusionlists", [])

    checked_fusionlists_genes_dict: list[dict] = store.isgl_handler.get_isgl_by_ids(
        checked_fusionlists
    )
    genes_covered_in_panel, filter_genes = util.common.get_sample_effective_genes(
        sample, assay_panel_doc, checked_fusionlists_genes_dict
    )

    # filter_fusionlist = util.fusion.create_fusiongenelist(fusionlist_filter)
    filter_fusion_effects = util.rna.create_fusioneffectlist(
        sample_filters.get("fusion_effects", [])
    )

    # Add them to the form and update with the requested settings
    form_data = deepcopy(sample_filters)
    form_data.update(
        {
            **{f"fusioncaller_{k}": True for k in fusion_callers},
            **{f"fusioneffect_{k}": True for k in fusion_effects},
            **{f"fusionlist_{k}": True for k in checked_fusionlists},
            **{assay_group: True},
        }
    )
    form.process(data=form_data)

    ## Change this to fusionquery.py

    query = build_fusion_query(
        assay_group,
        settings={
            "id": str(sample["_id"]),
            "min_spanning_reads": sample_filters["min_spanning_reads"],
            "min_spanning_pairs": sample_filters["min_spanning_pairs"],
            "fusion_effects": fusion_effects,
            "fusion_callers": fusion_callers,
            "checked_fusionlists": checked_fusionlists,
        },
    )

    app.logger.debug(f"Fusion query: {query}")
    print(f"assay_group: {assay_group}")
    print(f"Fusion query: {query}")

    fusions = list(store.fusion_handler.get_sample_fusions(query))

    # for fus_idx, fus in enumerate(fusions):
    #     # app.logger.info(f"these are fus, {fus_idx} {fus}")
    #     (
    #         fusions[fus_idx]["global_annotations"],
    #         fusions[fus_idx]["classification"],
    #     ) = store.fusion_handler.get_fusion_annotations(fusions[fus_idx])

    fusions, tiered_fusions = util.dna.add_global_annotations(fusions, assay_group, subpanel)

    app.logger.info(f"this is the fusion and fusion query,{query}")

    # TODO: load them as a display_sections_data instead of attaching to sample
    sample["expr"] = store.rna_expression_handler.get_rna_expression(str(sample["_id"]))
    sample["classification"] = store.rna_classification_handler.get_rna_classification(
        str(sample["_id"])
    )
    sample["QC_metrics"] = store.rna_qc_handler.get_rna_qc(str(sample["_id"]))

    # Your logic for handling RNA samples
    return render_template(
        "list_fusions.html",
        sample=sample,
        form=form,
        fusions=fusions,
        hidden_comments=has_hidden_comments,
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
    fusion = store.fusion_handler.get_fusion(fusion_id)

    result = get_sample_and_assay_config(sample_id)
    if isinstance(result, Response):
        return result
    sample, assay_config, assay_config_schema = result

    # Get assay group and subpanel for the sample, sections to display
    assay_group: str = assay_config.get("asp_group", "unknown")  # myeloid, solid, lymphoid
    subpanel: str | None = sample.get("subpanel")  # breast, LP, lung, etc.

    # Get sample data if the fusion is present in other samples
    in_other = store.fusion_handler.get_fusion_in_other_samples(fusion)

    # annotations, latest_classification = store.fusion_handler.get_fusion_annotations(fusion)
    # Get global annotations for the fusion

    selected_fusion_call = util.rna.get_selected_fusioncall(fusion)
    (
        annotations,
        latest_classification,
        other_classifications,
        annotations_interesting,
    ) = store.annotation_handler.get_global_annotations(selected_fusion_call, assay_group, subpanel)

    if not latest_classification or latest_classification.get("class") == 999:
        fusion = util.dna.add_alt_class(fusion, assay_group, subpanel)
    else:
        fusion["additional_classifications"] = None

    # Check if variant has hidden comments
    has_hidden_comments = store.fusion_handler.hidden_fusion_comments(fusion_id)

    # Get assay groups mappings with the sample assay
    assay_group_mappings = store.asp_handler.get_asp_group_mappings()

    # get all the fusion callsers to the top level in the fusion doc
    fusion["fusion_callers"] = util.rna.get_fusion_callers(fusion)

    return render_template(
        "show_fusion.html",
        fusion=fusion,
        in_other=in_other,
        sample=sample,
        annotations=annotations,
        latest_classification=latest_classification,
        annotations_interesting=annotations_interesting,
        other_classifications=other_classifications,
        hidden_comments=has_hidden_comments,
        assay_group=assay_group,
        subpanel=subpanel,
        assay_group_mappings=assay_group_mappings,
    )


@rna_bp.route("/<string:sample_id>/fusion/fp/<string:fus_id>", methods=["POST"])
@require_sample_access("sample_id")
def mark_false_fusion(sample_id: str, fus_id: str) -> Response:
    """
    Mark the specified RNA fusion event as a false positive in the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        fus_id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the fusion details page after updating the status.

    """
    store.fusion_handler.mark_false_positive_fusion(fus_id)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/unfp/<string:fus_id>", methods=["POST"])
@require_sample_access("sample_id")
def unmark_false_fusion(sample_id: str, fus_id: str) -> Response:
    """
    Unmark the False Positive status of a fusion event in the database.

    Args:
        sample_id (str): The unique identifier of the sample.
        fus_id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the fusion details page after updating the status.
    """
    store.fusion_handler.unmark_false_positive_fusion(fus_id)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route(
    "/<string:sample_id>/fusion/pickfusioncall/<string:fus_id>/<string:callidx>/<string:num_calls>",
    methods=["GET", "POST"],
)
@require_sample_access("sample_id")
def pick_fusioncall(sample_id: str, fus_id: str, callidx: str, num_calls: str) -> Response:
    """
    Pick a specific fusion call for a fusion event.

    Args:
        sample_id (str): The unique identifier of the sample.
        fus_id (str): The unique identifier of the fusion event.
        callidx (str): The index of the fusion call to pick.
        num_calls (str): The total number of fusion calls.

    Returns:
        Response: Redirects to the fusion details page after updating the picked call.
    """
    store.fusion_handler.pick_fusion(id, callidx, num_calls)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/hide_fusion_comment/<string:fus_id>", methods=["POST"])
@require_sample_access("sample_id")
def hide_fusion_comment(sample_id: str, fus_id: str) -> Response:
    """
    Hide a comment associated with a fusion event.

    Args:
        sample_id (str): The unique identifier of the sample.
        fus_id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the variant details page after hiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.fusion_handler.hide_fus_comment(fus_id, comment_id)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


@rna_bp.route("/<string:sample_id>/fusion/unhide_fusion_comment/<string:fus_id>", methods=["POST"])
@require_sample_access("sample_id")
def unhide_fusion_comment(sample_id: str, fus_id: str) -> Response:
    """
    Unhide a previously hidden comment associated with a fusion event.

    Args:
        sample_id (str): The unique identifier of the sample.
        fus_id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the variant details page after unhiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.fusion_handler.unhide_fus_comment(fus_id, comment_id)
    return redirect(url_for("rna_bp.show_fusion", sample_id=sample_id, fusion_id=fus_id))


##### PREVIEW REPORT ####
@rna_bp.route("/sample/preview_report/<string:sample_id>", methods=["GET", "POST"])
@require_sample_access("sample_id")
def generate_rna_report(sample_id, *args, **kwargs):
    """
    Generate a preview report for RNA fusion events associated with a sample.

    Args:
        sample_id (str): The unique identifier of the sample.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments. If 'pdf' is set, indicates PDF generation.

    Returns:
        Response: Rendered HTML template for the RNA fusion report preview.
    """
    sample = store.sample_handler.get_sample(sample_id)

    if not sample:
        sample = store.sample_handler.get_sample_with_id(sample_id)  # id = id

    # print (sample)
    assay = util.common.get_assay_from_sample(sample)

    app.logger.info(f"sample : {sample}")

    fusion_query = {"SAMPLE_ID": str(sample["_id"])}
    # app.logger.info(f"fusion_query : {fusion_query}")

    fusions = list(store.fusion_handler.get_sample_fusions(fusion_query))

    for fus_idx, fus in enumerate(fusions):
        # app.logger.info(f"these are fus, {fus_idx} {fus}")
        (
            fusions[fus_idx]["global_annotations"],
            fusions[fus_idx]["classification"],
        ) = store.fusion_handler.get_fusion_annotations(fusions[fus_idx])

    class_desc = list(app.config.get("REPORT_CONFIG").get("CLASS_DESC").values())
    class_desc_short = list(app.config.get("REPORT_CONFIG").get("CLASS_DESC_SHORT").values())
    analysis_desc = app.config.get("REPORT_CONFIG").get("ANALYSIS_DESCRIPTION", {}).get(assay)

    # app.logger.info(f"analysis_desc,{analysis_desc}")
    # app.logger.info(f"fusions,{fusions}")
    analysis_method = util.common.get_analysis_method(assay)
    report_header = util.common.get_report_header(assay, sample)
    report_date = datetime.now().date()
    pdf = kwargs.get("pdf", 0)

    return render_template(
        "report_fusion.html",
        assay=assay,
        fusions=fusions,
        report_header=report_header,
        analysis_method=analysis_method,
        analysis_desc=analysis_desc,
        sample=sample,
        class_desc=class_desc,
        class_desc_short=class_desc_short,
        report_date=report_date,
        pdf=pdf,
    )


@rna_bp.route("/sample/report/pdf/<string:sample_id>")
@require_sample_access("sample_id")
def generate_report_pdf(sample_id):
    """
    Generate a PDF report for the specified RNA sample.

    Args:
        sample_id (str): The unique identifier of the RNA sample.

    Returns:
        Response: A PDF file generated from the RNA sample report.
    """
    sample = store.sample_handler.get_sample(sample_id)  # id = name

    if not sample:
        sample = store.sample_handler.get_sample_with_id(sample_id)

    assay = util.common.get_assay_from_sample(sample)

    # Get report number
    report_num = 1
    if "report_num" in sample:
        report_num = sample["report_num"] + 1

    # PDF file name
    pdf_file = "static/reports/" + id + "_" + str(report_num) + ".pdf"

    # Generate PDF
    html = ""
    html = generate_rna_report(id, pdf=1)
    HTML(string=html).write_pdf(pdf_file)

    # Add to database
    store.sample_handler.get_sample(id).update(
        {"name": id},
        {
            "$push": {
                "reports": {
                    "_id": ObjectId(),
                    "report_num": report_num,
                    "filepath": pdf_file,
                    "author": current_user.get_id(),
                    "time_created": datetime.now(),
                }
            },
            "$set": {"report_num": report_num},
        },
    )

    # Render it!
    return render_pdf(HTML(string=html))


@rna_bp.route("/multi_class/<sample_id>", methods=["POST"])
@require_sample_access("sample_id")
def classify_multi_variant(sample_id: str) -> Response:
    """
    Classify multiple variants for a given sample.

    This view processes a POST request containing a list of selected variant IDs and classification actions.
    It supports applying or removing classification tiers, marking variants as irrelevant or false positive,
    and updates the database accordingly.

    Args:
        sample_id (str): The unique identifier of the sample whose variants are being classified.

    Returns:
        Response: Redirects to the fusion list page after processing the classification actions.
    """

    action = request.form.get("action")

    variants_to_modify = request.form.getlist("selected_object_id")
    assay = request.form.get("assay", None)
    subpanel = request.form.get("subpanel", None)
    tier = request.form.get("tier", None)
    irrelevant = request.form.get("irrelevant", None)
    false_positive = request.form.get("false_positive", None)

    if tier and action == "apply":
        variants_iter = []
        for variant in variants_to_modify:
            var_iter = store.variant_handler.get_variant(str(variant))
            variants_iter.append(var_iter)

        for var in variants_iter:
            selectec_csq = var["INFO"]["selected_CSQ"]
            transcript = selectec_csq.get("Feature", None)
            gene = selectec_csq.get("SYMBOL", None)
            hgvs_p = selectec_csq.get("HGVSp", None)
            hgvs_c = selectec_csq.get("HGVSc", None)
            hgvs_g = f"{var['CHROM']}:{var['POS']}:{var['REF']}/{var['ALT']}"
            consequence = selectec_csq.get("Consequence", None)
            gene_oncokb = store.oncokb_handler.get_oncokb_gene(gene)
            text = util.bpcommon.create_annotation_text_from_gene(
                gene, consequence, assay, gene_oncokb=gene_oncokb
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
                "assay": assay,
                "subpanel": subpanel,
                "transcript": transcript,
            }

            # Add the variant to the database with class
            store.annotation_handler.insert_classified_variant(
                variant, nomenclature, tier, variant_data
            )

            # Add the annotation text to the database
            store.annotation_handler.insert_classified_variant(
                variant, nomenclature, tier, variant_data, text=text
            )
            if irrelevant:
                store.variant_handler.mark_irrelevant_var(var["_id"])
    elif false_positive:
        if action == "apply":
            for variant in variants_to_modify:
                store.variant_handler.mark_false_positive_var(variant)
        elif action == "remove":
            for variant in variants_to_modify:
                store.variant_handler.unmark_false_positive_var(variant)
    elif irrelevant:
        if action == "apply":
            for variant in variants_to_modify:
                store.variant_handler.mark_irrelevant_var(variant)
        elif action == "remove":
            for variant in variants_to_modify:
                store.variant_handler.unmark_irrelevant_var(variant)
    return redirect(url_for("rna_bp.list_fusions", sample_id=sample_id))
