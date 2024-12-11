"""
Coyote case fusions
"""

from flask import abort
from flask import current_app as app
from flask import redirect, render_template, request, url_for, send_from_directory,flash, abort
from flask_login import current_user, login_required

from coyote.blueprints.dna.forms import FusionFilter
from wtforms import BooleanField
from wtforms.validators import Optional
from coyote.extensions import store,util
from coyote.blueprints.rna import rna_bp, filters
from typing import Literal, Any
from datetime import datetime
from flask_weasyprint import HTML, render_pdf


@rna_bp.route("/sample/<string:id>", methods=["GET", "POST"])
@login_required
def list_fusions(id):
    """
    Creates a functional elements to the fusion displays

    Parameters:
    id (str) : Sample id

    Returns:


    """
    sample = store.sample_handler.get_sample(id)

    if sample is None:
        sample = store.sample_handler.get_sample_with_id(id)

    sample_groups = sample.get("groups")
    if len(sample_groups) > 1:
        for group in sample_groups:
            if group in ["tumwgs-solid", "tumwgs-hema"]:
                smp_grp = group
                break
    else:
        smp_grp = sample["groups"][0]

    group_params = util.common.get_group_parameters(smp_grp)
    settings = util.common.get_group_defaults(group_params)
    assay = util.common.get_assay_from_sample(sample)

    app.logger.info(app.config["GROUP_CONFIGS"])  # get group config from app config instead
    app.logger.info(f"the sample has these groups {smp_grp}")
    app.logger.info(f"this is the group from collection {group_params}")

    gene_lists, genelists_assay = store.panel_handler.get_assay_panels(assay)
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
            store.sample_handler.update_sample_settings(_id, form)
            ## get sample again to recieve updated forms!
            sample = store.sample_handler.get_sample_with_id(_id)
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
    # print(fusionlist_filter)
    # print (filter_fusionlist)
    # print(filter_fusioneffects)

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
        (fusions[fus_idx]["global_annotations"], fusions[fus_idx]["classification"]) = (
            store.fusion_handler.get_fusion_annotations(fusions[fus_idx])
        )

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
def show_fusion(id):

    fusion = store.fusion_handler.get_fusion(id)
    sample = store.sample_handler.get_sample_with_id(fusion["SAMPLE_ID"])
    annotations, classification = store.fusion_handler.get_fusion_annotations(fusion)
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
@rna_bp.route("/sample/preview_report/<string:id>",  methods=['GET', 'POST'])
@login_required
def generate_rna_report(id, *args, **kwargs):

    sample = store.sample_handler.get_sample(id) 

    if not sample:
        sample = store.sample_handler.get_sample_with_id(id)  # id = id
    
    #print (sample)
    assay = util.common.get_assay_from_sample(sample)

    app.logger.info(f"sample : {sample}")

    fusion_query = {"SAMPLE_ID": str(sample["_id"])}
    #app.logger.info(f"fusion_query : {fusion_query}")
    
    fusions = list(store.fusion_handler.get_sample_fusions(fusion_query))
   

    for fus_idx, fus in enumerate(fusions):
        # app.logger.info(f"these are fus, {fus_idx} {fus}")
        (fusions[fus_idx]["global_annotations"], fusions[fus_idx]["classification"]) = (
            store.fusion_handler.get_fusion_annotations(fusions[fus_idx])
        )

    class_desc=list(app.config.get("REPORT_CONFIG").get("CLASS_DESC").values())
    class_desc_short = list(app.config.get("REPORT_CONFIG").get("CLASS_DESC_SHORT").values())
    analysis_desc= app.config.get("REPORT_CONFIG").get("ANALYSIS_DESCRIPTION", {}).get(assay)

    #app.logger.info(f"analysis_desc,{analysis_desc}")
    #app.logger.info(f"fusions,{fusions}")
    analysis_method = util.common.get_analysis_method(assay)
    report_header = util.common.get_report_header(assay, sample)
    report_date = datetime.now().date()
    pdf = kwargs.get('pdf', 0)
    
    return render_template(
        "report_fusion.html",
        assay=assay ,
        fusions=fusions,
        report_header=report_header,
        analysis_method=analysis_method,
        analysis_desc=analysis_desc,
        sample=sample, 
        class_desc=class_desc,
        class_desc_short=class_desc_short,
        report_date=report_date, 
        pdf=pdf
    )


@rna_bp.route('/sample/report/pdf/<string:id>')
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

