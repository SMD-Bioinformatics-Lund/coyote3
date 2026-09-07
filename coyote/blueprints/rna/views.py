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
from coyote.blueprints.rna import rna_bp
from datetime import datetime
from flask_weasyprint import HTML, render_pdf
from coyote.util.decorators.access import require_sample_access


@rna_bp.route("/sample/<string:id>K=", methods=["GET", "POST"])
@require_sample_access("sample_id")
def list_fusions(id: str) -> str | Response:
    """
    Display and filter RNA fusion events for a given sample.

    This view handles both GET and POST requests to display fusion events
    for the specified sample. It supports dynamic filtering of fusions
    based on user input, manages sample group and assay configuration,
    and prepares data for rendering the fusion list template.

    Parameters:
        id (str): The sample identifier.

    Returns:
        Response: Rendered HTML template for the fusion list page.
    """
    sample = store.sample_handler.get_sample(id)
    assay_config_schema = {}

    if sample is None:
        sample = store.sample_handler.get_sample_by_id(id)

    smp_grp = sample.get("assay", "unknown")

    group_params = util.common.get_group_parameters(smp_grp)
    settings = util.common.get_group_defaults(group_params)
    assay = util.common.get_assay_from_sample(sample)

    app.logger.info(app.config["GROUP_CONFIGS"])  # get group config from app config instead
    app.logger.info(f"the sample has these groups {smp_grp}")
    app.logger.info(f"this is the group from collection {group_params}")

    gene_lists, genelists_assay = store.asp_handler.get_assay_panels(assay)
    app.logger.info(f"this is the gene_lists, genelists_assay {gene_lists},{genelists_assay}")

    # Save new filter settings if submitteds
    # Inherit FilterForm, pass all genepanels from mongodb, set as boolean, NOW IT IS DYNAMIC!

    form = FusionFilter()
    ##
    ###########################################################################
    ## FORM FILTERS ##
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        _id = str(sample.get("_id"))
        # Reset filters to defaults
        if form.reset.data == True:
            print("does it go throu this?")
            store.sample_handler.reset_sample_settings(_id, settings)  ## this loop is not working
        # Change filters
        else:
            store.sample_handler.update_sample_filters(_id, form, assay_config_schema)
            ## get sample again to recieve updated forms!
            sample = store.sample_handler.get_sample_by_id(_id)
    ############################################################################
    # Check if sample has hidden comments
    has_hidden_comments = 1 if store.sample_handler.hidden_sample_comments(sample.get("_id")) else 0

    sample_settings = util.common.get_fusions_settings(sample, settings)

    fusionlist_filter = sample.get("checked_fusionlists", settings["default_checked_fusionlists"])
    fusioneffect_filter = sample.get(
        "checked_fusioneffects", settings["default_checked_fusioneffects"]
    )
    fusioncaller_filter = sample.get(
        "checked_fusioncallers", settings["default_checked_fusioncallers"]
    )

    # filter_fusionlist = util.fusion.create_fusiongenelist(fusionlist_filter)
    filter_fusioneffects = util.rna.create_fusioneffectlist(fusioneffect_filter)
    filter_fusioncaller = util.rna.create_fusioncallers(fusioncaller_filter)

    # app.logger.info(f"this is the sample {sample}")
    app.logger.info(f"this is the form data {form.data}")
    app.logger.info(f"this is the sample and settings  {settings}")
    app.logger.info(f"this is the sample_settings {sample_settings}")

    # app.logger.info(f"this is the sample,{sample}")
    ## Change this to fusionquery.py
    if assay == "fusion" or assay == "fusionrna":
        fusion_query = {
            "SAMPLE_ID": str(sample["_id"]),
            "calls": {
                "$elemMatch": {
                    "spanreads": {"$gte": sample_settings["min_spanreads"]},
                    "spanpairs": {"$gte": sample_settings["min_spanpairs"]},
                }
            },
        }
        if fusioneffect_filter:
            fusion_query["calls.effect"] = {"$in": filter_fusioneffects}
        if filter_fusioncaller:
            fusion_query["calls.caller"] = {"$in": filter_fusioncaller}
        if "fusionlist_FCknown" in fusionlist_filter:
            fusion_query["calls.desc"] = {"$regex": "known"}
        if "fusionlist_mitelman" in fusionlist_filter:
            fusion_query["calls.desc"] = {"$regex": "mitelman"}

        fusions = list(store.fusion_handler.get_sample_fusions(fusion_query))

    for fus_idx, fus in enumerate(fusions):
        # app.logger.info(f"these are fus, {fus_idx} {fus}")
        (
            fusions[fus_idx]["global_annotations"],
            fusions[fus_idx]["classification"],
        ) = store.fusion_handler.get_fusion_annotations(fusions[fus_idx])

    app.logger.info(f"this is the fusion and fusion query,{fusions},{fusion_query}")

    # Your logic for handling RNA samples
    return render_template(
        "list_fusions.html",
        sample=sample,
        form=form,
        fusions=fusions,
        hidden_comments=has_hidden_comments,
        sample_id=sample["_id"],
    )


@rna_bp.route("/fusion/<string:id>")
@login_required
def show_fusion(id: str) -> Response:
    """
    Display details for a specific RNA fusion event.

    Retrieves the fusion by its ID, fetches the associated sample, obtains
    annotations and classification for the fusion, and renders the
    show_fusion.html template with this data.

    Args:
        id (str): The unique identifier of the fusion event.

    Returns:
        Response: Rendered HTML template with fusion, sample, annotations,
        and classification data.
    """
    fusion = store.fusion_handler.get_fusion(id)
    sample = store.sample_handler.get_sample_by_id(fusion["SAMPLE_ID"])

    annotations, classification = store.fusion_handler.get_fusion_annotations(fusion)
    return render_template(
        "show_fusion.html",
        fusion=fusion,
        sample=sample,
        annotations=annotations,
        classification=classification,
    )


@rna_bp.route("/fusion/fp/<string:id>", methods=["POST"])
@login_required
def mark_false_fusion(id: str) -> Response:
    """
    Mark the specified RNA fusion event as a false positive in the database.

    Args:
        id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the fusion details page after updating the status.

    """
    store.fusion_handler.mark_false_positive_fusion(id)
    return redirect(url_for("rna_bp.show_fusion", id=id))


@rna_bp.route("/fusion/unfp/<string:id>", methods=["POST"])
@login_required
def unmark_false_fusion(id: str) -> Response:
    """
    Unmark the False Positive status of a fusion event in the database.

    Args:
        id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the fusion details page after updating the status.
    """
    store.fusion_handler.unmark_false_positive_fusion(id)
    return redirect(url_for("rna_bp.show_fusion", id=id))


@rna_bp.route(
    "/fusion/pickfusioncall/<string:id>/<string:callidx>/<string:num_calls>",
    methods=["GET", "POST"],
)
@login_required
def pick_fusioncall(id: str, callidx: str, num_calls: str) -> Response:
    """
    Pick a specific fusion call for a fusion event.

    Args:
        id (str): The unique identifier of the fusion event.
        callidx (str): The index of the fusion call to pick.
        num_calls (str): The total number of fusion calls.

    Returns:
        Response: Redirects to the fusion details page after updating the picked call.
    """
    store.fusion_handler.pick_fusion(id, callidx, num_calls)
    return redirect(url_for("rna_bp.show_fusion", id=id))


@rna_bp.route("/fusion/hide_fusion_comment/<string:fus_id>", methods=["POST"])
@login_required
def hide_fusion_comment(fus_id: str) -> Response:
    """
    Hide a comment associated with a fusion event.

    Args:
        fus_id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the variant details page after hiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.fusion_handler.hide_fus_comment(var_id, comment_id)
    return redirect(url_for("rna_bp.show_variant", id=var_id))


@rna_bp.route("/var/unhide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def unhide_fusion_comment(var_id: str) -> Response:
    """
    Unhide a previously hidden comment associated with a fusion event.

    Args:
        var_id (str): The unique identifier of the fusion event.

    Returns:
        Response: Redirects to the variant details page after unhiding the comment.
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.fusion_handler.unhide_fus_comment(var_id, comment_id)
    return redirect(url_for("rna_bp.show_variant", id=var_id))


##### PREVIEW REPORT ####
@rna_bp.route("/sample/preview_report/<string:id>", methods=["GET", "POST"])
@login_required
def generate_rna_report(id, *args, **kwargs):
    """
    Generate a preview report for RNA fusion events associated with a sample.

    Args:
        id (str): The unique identifier of the sample.
        *args: Additional positional arguments.
        **kwargs: Additional keyword arguments. If 'pdf' is set, indicates PDF generation.

    Returns:
        Response: Rendered HTML template for the RNA fusion report preview.
    """
    sample = store.sample_handler.get_sample(id)

    if not sample:
        sample = store.sample_handler.get_sample_with_id(id)  # id = id

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
    report_date = util.common.utc_now().date()
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


@rna_bp.route("/sample/report/pdf/<string:id>")
@login_required
def generate_report_pdf(id):
    """
    Generate a PDF report for the specified RNA sample.

    Args:
        id (str): The unique identifier of the RNA sample.

    Returns:
        Response: A PDF file generated from the RNA sample report.
    """
    sample = store.sample_handler.get_sample(id)  # id = name

    if not sample:
        sample = store.sample_handler.get_sample_with_id(id)

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
                    "time_created": util.common.utc_now(),
                }
            },
            "$set": {"report_num": report_num},
        },
    )

    # Render it!
    return render_pdf(HTML(string=html))


@rna_bp.route("/multi_class/<id>", methods=["POST"])
@login_required
def classify_multi_variant(id: str) -> Response:
    """
    Classify multiple variants for a given sample.

    This view processes a POST request containing a list of selected variant IDs and classification actions.
    It supports applying or removing classification tiers, marking variants as irrelevant or false positive,
    and updates the database accordingly.

    Args:
        id (str): The unique identifier of the sample whose variants are being classified.

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
    return redirect(url_for("rna_bp.list_fusions", id=id))
