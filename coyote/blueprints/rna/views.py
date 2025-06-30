"""
Coyote case fusions
"""

from copy import deepcopy
from datetime import datetime

from flask import (
    abort,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask import current_app as app
from flask_login import current_user, login_required
from flask_weasyprint import HTML, render_pdf
from werkzeug import Response

from coyote.blueprints.dna.forms import FusionFilter
from coyote.blueprints.rna import filters, rna_bp

# from wtforms import BooleanField
# from wtforms.validators import Optional
from coyote.extensions import store, util
from coyote.services.auth.decorators import require
from coyote.util.decorators.access import require_sample_access
from coyote.util.misc import get_sample_and_assay_config


@rna_bp.route("/sample/<string:sample_id>", methods=["GET", "POST"])
@login_required
@require_sample_access("sample_id")
def list_fusions(sample_id):
    """
    Creates a functional elements to the fusion displays

    Parameters:
    id (str) : Sample id

    Returns:


    """
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

    # Get the entire genelist for the sample panel
    assay_panel_doc = store.asp_handler.get_asp(asp_name=sample_assay)

    # Get the genelists for the sample panel
    insilico_panel_genelists = store.isgl_handler.get_isgl_by_asp(
        sample_assay, is_active=True
    )
    all_panel_genelist_names = util.common.get_assay_genelist_names(
        insilico_panel_genelists
    )

    # Adding the default gene lists to the assay_config, if use_diagnosis_genelist is set to true
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


    form = FusionFilter()
  
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

        ## get sample again to recieve updated forms!
        sample = store.sample_handler.get_sample_by_id(_id)
        sample_filters = deepcopy(sample.get("filters"))

    ############################################################################
    # Check if the sample has hidden comments
    has_hidden_comments = store.sample_handler.hidden_sample_comments(
        sample.get("_id")
    )
    
    app.logger.info(
        f"this is the filters in the sample {sample_filters}"
    )


    checked_fusionlists  = sample_filters.get("fusionlists", [])
    checked_fusioncallers = sample_filters.get("fusion_callers", [])
    checked_fusioneffects = sample_filters.get("fusion_effects", [])


    app.logger.info(f"this is the form list {checked_fusionlists} {checked_fusioncallers} {checked_fusioneffects}")


    fusion_query = { 
        "SAMPLE_ID": str(sample["_id"]),
        "calls": {
            "$elemMatch": {
                "spanreads": {"$gte": sample_filters["spanning_reads"]},
                "spanpairs": {"$gte": sample_filters["spanning_pairs"]},
                }
            },
        }
        # if fusioneffect_filter:
        #     fusion_query["calls.effect"] = {"$in": sample_filters["fusion_effect"]}
        # if filter_fusioncaller:
        #     fusion_query["calls.caller"] = {"$in": sample_filters["fusion_callers"]}
        # if "fusionlist_FCknown" in sample_filters["fusion_list"]:
        #     fusion_query["calls.desc"] = {"$regex": "known"}
        # if "fusionlist_mitelman" in fusionlist_filter:
        #     fusion_query["calls.desc"] = {"$regex": "mitelman"}

    fusions = list(store.fusion_handler.get_sample_fusions(fusion_query))

    for fus_idx, fus in enumerate(fusions):
        # app.logger.info(f"these are fus, {fus_idx} {fus}")
        (
            fusions[fus_idx]["global_annotations"],
            fusions[fus_idx]["classification"],
        ) = store.fusion_handler.get_fusion_annotations(fusions[fus_idx])

    app.logger.info(
        f"this is the fusion and fusion query,{fusions},{fusion_query}"
    )

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
def show_fusion(id):
    fusion = store.fusion_handler.get_fusion(id)
    sample = store.sample_handler.get_sample_by_id(fusion["SAMPLE_ID"])
    print("SAMPLE")
    print(sample)

    annotations, classification = store.fusion_handler.get_fusion_annotations(
        fusion
    )
    print(annotations)
    print(classification)

    return render_template(
        "show_fusion.html",
        fusion=fusion,
        sample=sample,
        annotations=annotations,
        classification=classification,
    )


@rna_bp.route("/fusion/fp/<string:id>", methods=["POST"])
@login_required
def mark_false_fusion(id):
    """
    Mark False Positive status of a variant in the database
    """
    store.fusion_handler.mark_false_positive_fusion(id)
    return redirect(url_for("rna_bp.show_fusion", id=id))


@rna_bp.route("/fusion/unfp/<string:id>", methods=["POST"])
@login_required
def unmark_false_fusion(id):
    """
    Unmark False Positive status of a variant in the database
    """
    store.fusion_handler.unmark_false_positive_fusion(id)
    return redirect(url_for("rna_bp.show_fusion", id=id))


@rna_bp.route(
    "/fusion/pickfusioncall/<string:id>/<string:callidx>/<string:num_calls>",
    methods=["GET", "POST"],
)
@login_required
def pick_fusioncall(id, callidx, num_calls):
    store.fusion_handler.pick_fusion(id, callidx, num_calls)
    return redirect(url_for("rna_bp.show_fusion", id=id))


@rna_bp.route("/fusion/hide_fusion_comment/<string:fus_id>", methods=["POST"])
@login_required
def hide_fusion_comment(fus_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.fusion_handler.hide_fus_comment(var_id, comment_id)
    return redirect(url_for("rna_bp.show_variant", id=var_id))


@rna_bp.route("/var/unhide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def unhide_fusion_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.fusion_handler.unhide_fus_comment(var_id, comment_id)
    return redirect(url_for("rna_bp.show_variant", id=var_id))


##### PREVIEW REPORT ####
@rna_bp.route("/sample/preview_report/<string:id>", methods=["GET", "POST"])
@login_required
def generate_rna_report(id, *args, **kwargs):
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

    class_desc = list(
        app.config.get("REPORT_CONFIG").get("CLASS_DESC").values()
    )
    class_desc_short = list(
        app.config.get("REPORT_CONFIG").get("CLASS_DESC_SHORT").values()
    )
    analysis_desc = (
        app.config.get("REPORT_CONFIG")
        .get("ANALYSIS_DESCRIPTION", {})
        .get(assay)
    )

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


@rna_bp.route("/sample/report/pdf/<string:id>")
@login_required
def generate_report_pdf(id):
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
                    "time_created": datetime.now(),
                }
            },
            "$set": {"report_num": report_num},
        },
    )

    # Render it!
    return render_pdf(HTML(string=html))


@rna_bp.route("/multi_class/<id>", methods=["POST"])
@login_required
def classify_multi_variant(id):
    """
    Classify multiple variants
    """
    print(f"var_form: {request.form.to_dict()}")
    action = request.form.get("action")
    print(f"action: {action}")
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
            text = util.dna.create_annotation_text_from_gene(
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
