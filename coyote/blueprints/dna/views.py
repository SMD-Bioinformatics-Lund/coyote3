"""
Coyote case variants
"""

from flask import current_app as app
from flask import redirect, render_template, request, url_for, send_from_directory, flash, abort
from flask_login import current_user, login_required
from pprint import pformat
from wtforms import BooleanField
from coyote.extensions import store, util
from coyote.blueprints.dna import dna_bp, varqueries_notbad, filters
from coyote.blueprints.home import home_bp
from coyote.blueprints.dna.varqueries import build_query
from coyote.blueprints.dna.forms import GeneForm
from coyote.errors.exceptions import AppError
from typing import Literal, Any
from datetime import datetime
from flask_weasyprint import HTML, render_pdf
import os


@dna_bp.route("/sample/<string:id>", methods=["GET", "POST"])
@login_required
def list_variants(id):

    # Find sample data by name
    sample = store.sample_handler.get_sample(id)  # id = name

    # Get sample data by id if name is none
    if sample is None:
        sample = store.sample_handler.get_sample_with_id(id)  # id = id

    # Get case and control samples
    sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))

    ## Check the length of the sample groups from db, and if len is more than one, tumwgs-solid or tumwgs-hema takes the priority in new coyote
    smp_grp = util.common.select_one_sample_group(sample.get("groups"))

    # Get group parameters from the sample group config file
    group_params = util.common.get_group_parameters(smp_grp)

    # Get group defaults from coyote config, if not found in group config
    settings = util.common.get_group_defaults(group_params)

    # Get assay from sample
    assay: str | None | Literal["unknown"] = util.common.get_assay_from_sample(sample)
    subpanel = sample.get("subpanel")

    # get group config from app config instead
    app.logger.debug(app.config["GROUP_CONFIGS"])
    app.logger.debug(f"the sample has these groups {smp_grp}")
    app.logger.debug(f"this is the group from collection {group_params}")

    ## GENEPANELS ##
    ## send over all defined gene panels per assay, to matching template ##
    gene_lists, genelists_assay = store.panel_handler.get_assay_panels(assay)
    ## Default gene list. For samples with default_genelis_set=1 add a gene list to specific subtypes lunga, hjärna etc etc. Will fetch genelist from mongo collection.
    # this only for assays that should have a default gene list. Will always be added to sample if not explicitely removed from form
    if "default_genelist_set" in group_params:
        if subpanel:
            panel_genelist = store.panel_handler.get_panel(subpanel=subpanel, type="genelist")
            if panel_genelist:
                settings["default_checked_genelists"] = {f"genelist_{subpanel}": 1}

    # Save new filter settings if submitted
    # Inherit FilterForm, pass all genepanels from mongodb, set as boolean, NOW IT IS DYNAMIC!
    for panel in genelists_assay:
        if panel["type"] == "genelist":
            setattr(GeneForm, "genelist_" + panel["name"], BooleanField())
    form = GeneForm()
    ###########################################################################

    ## FORM FILTERS ##
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        _id = str(sample.get("_id"))
        # Reset filters to defaults
        if form.reset.data:
            store.sample_handler.reset_sample_settings(_id, settings)
        # Change filters
        else:
            store.sample_handler.update_sample_settings(_id, form)
            ## get sample again to recieve updated forms!
            sample = store.sample_handler.get_sample_with_id(_id)

    ############################################################################

    # Check if sample has hidden comments
    has_hidden_comments = store.sample_handler.hidden_sample_comments(sample.get("_id"))

    ## get sample settings
    sample_settings = util.common.get_sample_settings(sample, settings)

    # sample filters, either set, or default
    cnv_effects = sample.get("checked_cnveffects", settings["default_checked_cnveffects"])
    genelist_filter = sample.get("checked_genelists", settings["default_checked_genelists"])
    filter_conseq = util.dna.get_filter_conseq_terms(sample_settings["csq_filter"].keys())
    filter_genes = util.common.create_filter_genelist(genelist_filter, gene_lists)
    filter_cnveffects = util.dna.create_cnveffectlist(cnv_effects)

    # Add them to the form
    form.min_freq.data = sample_settings["min_freq"]
    form.max_freq.data = sample_settings["max_freq"]
    form.min_depth.data = sample_settings["min_depth"]
    form.min_reads.data = sample_settings["min_reads"]
    form.max_popfreq.data = sample_settings["max_popfreq"]
    form.min_cnv_size.data = sample_settings["min_cnv_size"]
    form.max_cnv_size.data = sample_settings["max_cnv_size"]

    ## SNV FILTRATION STARTS HERE ! ##
    ##################################
    ## The query should really be constructed according to some configed rules for a specific assay
    query = build_query(
        assay,
        {
            "id": str(sample["_id"]),
            "max_freq": sample_settings["max_freq"],
            "min_freq": sample_settings["min_freq"],
            "min_depth": sample_settings["min_depth"],
            "min_reads": sample_settings["min_reads"],
            "max_popfreq": sample_settings["max_popfreq"],
            "filter_conseq": filter_conseq,
        },
    )
    query2 = varqueries_notbad.build_query(
        {
            "id": str(sample["_id"]),
            "max_freq": sample_settings["max_freq"],
            "min_freq": sample_settings["min_freq"],
            "min_depth": sample_settings["min_depth"],
            "min_reads": sample_settings["min_reads"],
            "max_popfreq": sample_settings["max_popfreq"],
            "filter_conseq": filter_conseq,
        },
        group_params,
    )

    app.logger.debug("this is the old varquery: %s", pformat(query))
    # app.logger.debug("this is the new varquery: %s", pformat(query2))

    variants_iter = store.variant_handler.get_case_variants(query)

    # Find all genes that are protein coding
    # variants, protein_coding_genes = util.dna.get_protein_coding_genes(variants_iter)

    variants = list(variants_iter)

    # Add blacklist data
    variants = store.blacklist_handler.add_blacklist_data(variants, assay)

    # Add global annotations for the variants
    variants = util.dna.add_global_annotations(variants, assay, subpanel)

    # Filter by population frequency
    variants = util.dna.popfreq_filter(variants, float(sample_settings["max_popfreq"]))

    # Add hotspot data
    variants = util.dna.hotspot_variant(variants)

    ### SNV FILTRATION ENDS HERE ###

    # LOWCOV data, very computationally intense for samples with many regions
    low_cov = store.coverage_handler.get_sample_coverage(sample["name"])
    low_cov_chrs = list(set([x["chr"] for x in low_cov]))

    ## add cosmic to lowcov regions. Too many lowcov regions and this becomes very slow
    # this could maybe be something else than cosmic? config important regions?
    cosmic_ids = store.cosmic_handler.get_cosmic_ids(chr=low_cov_chrs)

    if assay != "solid":
        low_cov = util.dna.filter_low_coverage_with_cosmic(low_cov, cosmic_ids)

    ## GET CNVs TRANSLOCS and OTHER BIOMARKERS ##
    cnvwgs_iter = False
    cnvwgs_iter_n = False
    biomarkers_iter = False
    transloc_iter = False
    if group_params is not None and "DNA" in group_params:
        if group_params["DNA"].get("CNV"):
            cnvwgs_iter = list(store.cnv_handler.get_sample_cnvs(sample_id=str(sample["_id"])))
            if filter_cnveffects:
                cnvwgs_iter = store.cnv_handler.cnvtype_variant(cnvwgs_iter, filter_cnveffects)
            cnvwgs_iter = store.cnv_handler.cnv_organizegenes(cnvwgs_iter)
            cnvwgs_iter_n = list(
                store.cnv_handler.get_sample_cnvs(sample_id=str(sample["_id"]), normal=True)
            )
        if group_params["DNA"].get("OTHER"):
            biomarkers_iter = store.biomarker_handler.get_sample_biomarkers(
                sample_id=str(sample["_id"])
            )
        if group_params["DNA"].get("FUSIONS"):
            transloc_iter = store.transloc_handler.get_sample_translocations(
                sample_id=str(sample["_id"])
            )
    #################################################

    ## "AI"-text depending on what analysis has been done. Add translocs and cnvs if marked as interesting (HRD and MSI?)
    ## SNVs, non-optional. Though only has rules for PARP + myeloid and solid
    ai_text = ""
    conclusion = ""
    # ai_text, conclusion = util.generate_ai_text( assay, variants, filter_genes, genelist_filter, sample["groups"][0] )
    ## translocations (DNA fusions) and copy number variation. Works for solid so far, should work for myeloid, lymphoid
    if assay == "solid":
        transloc_iter_ai = store.transloc_handler.get_sample_translocations(
            sample_id=str(sample["_id"])
        )
        biomarkers_iter_ai = store.biomarker_handler.get_sample_biomarkers(
            sample_id=str(sample["_id"])
        )
        ai_text_transloc = util.dna.generate_ai_text_nonsnv(
            assay, transloc_iter_ai, sample["groups"][0], "transloc"
        )
        ai_text_cnv = util.dna.generate_ai_text_nonsnv(
            assay, cnvwgs_iter, sample["groups"][0], "cnv"
        )
        ai_text_bio = util.dna.generate_ai_text_nonsnv(
            assay, biomarkers_iter_ai, sample["groups"][0], "bio"
        )
        ai_text = ai_text + ai_text_transloc + ai_text_cnv + ai_text_bio + conclusion
    else:
        ai_text = ai_text + conclusion

    # this is in config, but needs to be tested (2024-05-14) with a HD-sample of relevant name
    disp_pos = []
    if "verif_samples" in group_params:
        if sample["name"] in group_params["verif_samples"]:
            disp_pos = group_params["verif_samples"][sample["name"]]
    # this is to allow old samples to view plots, cnv + cnvprofile clash. Old assays used cnv as the entry for the plot, newer assays use cnv for path to cnv-file that was loaded.
    if "cnv" in sample:
        if sample["cnv"].lower().endswith((".png", ".jpg", ".jpeg")):
            sample["cnvprofile"] = sample["cnv"]

    return render_template(
        "list_variants_vep.html",
        checked_genelists=genelist_filter,
        genelists_assay=genelists_assay,
        variants=variants,
        disp_pos=disp_pos,
        sample=sample,
        sample_ids=sample_ids,
        assay=assay,
        hidden_comments=has_hidden_comments,
        form=form,
        dispgenes=filter_genes,
        low_cov=low_cov,
        ai_text=ai_text,
        settings=settings,
        cnvwgs=cnvwgs_iter,
        cnvwgs_n=cnvwgs_iter_n,
        sizefilter=sample_settings["max_cnv_size"],
        sizefilter_min=sample_settings["min_cnv_size"],
        transloc=transloc_iter,
        biomarker=biomarkers_iter,
    )


@dna_bp.route("/plot/<string:fn>/<string:assay>/<string:build>")  # type: ignore
def show_any_plot(fn, assay, build):
    if assay == "myeloid":
        if build == "38":
            return send_from_directory("/access/myeloid38/plots", fn)
        else:
            return send_from_directory("/access/myeloid/plots", fn)
    elif assay == "lymphoid":
        return send_from_directory("/access/lymphoid_hg38/plots", fn)
    elif assay == "gmsonco" or assay == "swea":
        return send_from_directory("/access/PARP_inhib/plots", fn)
    elif assay == "tumwgs":
        print(fn)
        return send_from_directory("/access/tumwgs/cov", fn)
    elif assay == "solid":
        return send_from_directory("/access/solid_hg38/plots", fn)


## Individual variant view ##
@dna_bp.route("/var/<string:id>")
@login_required
def show_variant(id):

    variant = store.variant_handler.get_variant(id)
    in_other = store.variant_handler.get_variant_in_other_samples(variant)
    sample = store.sample_handler.get_sample_with_id(variant["SAMPLE_ID"])

    assay = util.common.get_assay_from_sample(sample)
    subpanel = sample.get("subpanel")

    # Check if variant has hidden comments
    has_hidden_comments = store.variant_handler.hidden_var_comments(id)

    expression = store.expression_handler.get_expression_data(list(variant.get("transcripts")))

    variant = store.blacklist_handler.add_blacklist_data([variant], assay)[0]

    # Get canonical transcripts for all genes annotated for the variant
    # canonical_dict = store.canonical_handler.get_canonical_by_genes(list(variant.get("genes")))

    # Select a transcript
    # TODO: I DONT WANT TO RUN THE SAME COMMANDS MULTIPLE TIMES IN ORDER TO REDUCE THE PROCESSING SPEED, MAY BE STORE THE SELECT CSQ TRANSCRIPT ID IN THE VARIANT ITSELF
    # (variant["INFO"]["selected_CSQ"], variant["INFO"]["selected_CSQ_criteria"]) = (
    #     util.dna.select_csq(variant["INFO"]["CSQ"], canonical_dict)
    # )

    # Find civic data
    hgvsc_str = variant["INFO"]["selected_CSQ"]["HGVSc"]

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

    # Find OncoKB data
    oncokb_hgvsp = []
    if len(variant["INFO"]["selected_CSQ"]["HGVSp"]) > 0:
        # hgvsp = filters.one_letter_p(variant["INFO"]["selected_CSQ"]["HGVSp"]).split(":")[1]
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
    oncokb_action = store.oncokb_handler.get_oncokb_action(variant, oncokb_hgvsp)
    oncokb_gene = store.oncokb_handler.get_oncokb_gene(variant["INFO"]["selected_CSQ"]["SYMBOL"])

    # Find BRCA-exchange data
    brca_exchange = store.brca_handler.get_brca_data(variant, assay)

    # Find IARC TP53 data
    iarc_tp53 = store.iarc_tp53_handler.find_iarc_tp53(variant)

    # Get bams
    sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)

    # Format PON (panel of normals) data
    pon = util.dna.format_pon(variant)

    # Get global annotations for the variant
    annotations, classification, other_classifications, annotations_interesting = (
        store.annotation_handler.get_global_annotations(variant, assay, subpanel)
    )

    return render_template(
        "show_variant_vep.html",
        variant=variant,
        in_other=in_other,
        annotations=annotations,
        hidden_comments=has_hidden_comments,
        classification=classification,
        expression=expression,
        civic=civic,
        civic_gene=civic_gene,
        oncokb=oncokb,
        oncokb_action=oncokb_action,
        oncokb_gene=oncokb_gene,
        sample=sample,
        brca_exchange=brca_exchange,
        iarc_tp53=iarc_tp53,
        assay=assay,
        pon=pon,
        other_classifications=other_classifications,
        subpanel=subpanel,
        sample_ids=sample_ids,
        bam_id=bam_id,
        annotations_interesting=annotations_interesting,
    )


@dna_bp.route("/var/unfp/<string:id>", methods=["POST"])
@login_required
def unmark_false_variant(id):
    """
    Unmark False Positive status of a variant in the database
    """
    store.variant_handler.unmark_false_positive_var(id)
    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/fp/<string:id>", methods=["POST"])
@login_required
def mark_false_variant(id):
    """
    Mark False Positive status of a variant in the database
    """
    store.variant_handler.mark_false_positive_var(id)
    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/uninterest/<string:id>", methods=["POST"])
@login_required
def unmark_interesting_variant(id):
    """
    Unmark interesting status of a variant in the database
    """
    store.variant_handler.unmark_interesting_var(id)
    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/interest/<string:id>", methods=["POST"])
@login_required
def mark_interesting_variant(id):
    """
    Mark interesting status of a variant in the database
    """
    store.variant_handler.mark_interesting_var(id)
    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/unirrelevant/<string:id>", methods=["POST"])
@login_required
def unmark_irrelevant_variant(id):
    """
    Unmark irrelevant status of a variant in the database
    """
    store.variant_handler.unmark_irrelevant_var(id)
    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/irrelevant/<string:id>", methods=["POST"])
@login_required
def mark_irrelevant_variant(id):
    """
    Mark irrelevant status of a variant in the database
    """
    store.variant_handler.mark_irrelevant_var(id)
    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/blacklist/<string:id>", methods=["POST"])
@login_required
def add_variant_to_blacklist(id):

    var = store.variant_handler.get_variant(id)
    sample = store.sample_handler.get_sample_with_id(var["SAMPLE_ID"])
    assay = util.common.get_assay_from_sample(sample)
    store.blacklist_handler.blacklist_variant(var, assay)
    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/ordersanger/<string:id>", methods=["POST"])
@login_required
def order_sanger(id):
    variant = store.variant_handler.get_variant(id)
    variants, protein_coding_genes = util.dna.get_protein_coding_genes([variant])
    var = variants[0]
    sample = store.sample_handler.get_sample_with_id(var["SAMPLE_ID"])
    canonical_dict = store.canonical_handler.get_canonical_by_genes(list(protein_coding_genes))

    var["INFO"]["selected_CSQ"], var["INFO"]["selected_CSQ_criteria"] = util.select_csq(
        var["INFO"]["CSQ"], canonical_dict
    )

    html, tx_info = util.dna.compose_sanger_email(var, sample["name"])

    email_status = util.dna.send_sanger_email(html, tx_info["SYMBOL"])

    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/classify/<string:id>", methods=["POST"])
@login_required
def classify_variant(id):
    form_data = request.form.to_dict()
    class_num = util.dna.get_tier_classification(form_data)
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    if class_num != 0:
        store.annotation_handler.insert_classified_variant(
            variant, nomenclature, class_num, form_data
        )

    if class_num != 0:
        if nomenclature == "f":
            return redirect(url_for("rna_bp.show_fusion", id=id))

    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/rmclassify/<string:id>", methods=["POST"])
@login_required
def remove_classified_variant(id):
    form_data = request.form.to_dict()
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", id=id))
    per_assay = store.annotation_handler.delete_classified_variant(variant, nomenclature, form_data)
    app.logger.debug(per_assay)
    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/comment/<string:id>", methods=["POST"])
@login_required
def add_variant_comment(id):
    """
    Add a comment to a variant
    """

    # If global checkbox. Save variant with the protein, coding och genomic nomenclature in decreasing priority
    form_data = request.form.to_dict()
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    doc = util.dna.create_comment_doc(form_data, nomenclature=nomenclature, variant=variant)
    _type = form_data.get("global", None)
    if _type == "global":
        store.annotation_handler.add_anno_comment(doc)
        flash("Global comment added", "green")

    if nomenclature == "f":
        if _type != "global":
            store.fusion_handler.add_fusion_comment(id, doc)
        return redirect(url_for("rna_bp.show_fusion", id=id))
    elif nomenclature == "t":
        if _type != "global":
            store.transloc_handler.add_transloc_comment(id, doc)
        return redirect(url_for("dna_bp.show_transloc", id=id))
    elif nomenclature == "cn":
        if _type != "global":
            store.cnv_handler.add_cnv_comment(id, doc)
        return redirect(url_for("dna_bp.show_cnvwgs", id=id))
    else:
        if _type != "global":
            store.variant_handler.add_var_comment(id, doc)

    return redirect(url_for("dna_bp.show_variant", id=id))


@dna_bp.route("/var/hide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def hide_variant_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.variant_handler.hide_var_comment(var_id, comment_id)
    return redirect(url_for("dna_bp.show_variant", id=var_id))


@dna_bp.route("/var/unhide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def unhide_variant_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.variant_handler.unhide_variant_comment(var_id, comment_id)
    return redirect(url_for("dna_bp.show_variant", id=var_id))


###### CNVS VIEW PAGE #######
@dna_bp.route("/cnv/<string:id>")
@login_required
def show_cnv(id):
    """
    Show CNVs view page
    """
    cnv = store.cnv_handler.get_cnv(id)
    sample = store.sample_handler.get_sample_with_id((cnv["SAMPLE_ID"]))
    assay = util.common.get_assay_from_sample(sample)
    sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)
    hidden_cnv_comments = store.cnv_handler.hidden_cnv_comments(id)

    annotations = store.cnv_handler.get_cnv_annotations(cnv)
    return render_template(
        "show_cnvwgs.html",
        cnv=cnv,
        sample=sample,
        classification=999,
        annotations=annotations,
        sample_ids=sample_ids,
        bam_id=bam_id,
        hidden_comments=hidden_cnv_comments,
    )


@dna_bp.route("/cnv/uninterestcnv/<string:id>", methods=["POST"])
@login_required
def unmark_interesting_cnv(id):
    """
    Unmark CNV as interesting
    """
    store.cnv_handler.unmark_interesting_cnv(id)
    return redirect(url_for("dna_bp.show_cnv", id=id))


@dna_bp.route("/cnv/interestcnv/<string:id>", methods=["POST"])
@login_required
def mark_interesting_cnv(id):
    """
    Mark CNV as interesting
    """
    store.cnv_handler.mark_interesting_cnv(id)
    return redirect(url_for("dna_bp.show_cnv", id=id))


@dna_bp.route("/cnv/fpcnv/<string:id>", methods=["POST"])
@login_required
def mark_false_cnv(id):
    """
    Mark CNV as false positive
    """
    store.cnv_handler.mark_false_positive_cnv(id)
    return redirect(url_for("dna_bp.show_cnv", id=id))


@dna_bp.route("/cnv/unfpcnv/<string:id>", methods=["POST"])
@login_required
def unmark_false_cnv(id):
    """
    Unmark CNV as false positive
    """
    store.cnv_handler.unmark_false_positive_cnv(id)
    return redirect(url_for("dna_bp.show_cnv", id=id))


@dna_bp.route("/cnv/hide_variant_comment/<string:cnv_id>", methods=["POST"])
@login_required
def hide_cnv_comment(cnv_id):
    """
    Hide CNV comment
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.cnv_handler.hide_cnvs_comment(cnv_id, comment_id)
    return redirect(url_for("dna_bp.show_cnv", id=cnv_id))


@dna_bp.route("/cnv/unhide_variant_comment/<string:cnv_id>", methods=["POST"])
@login_required
def unhide_cnv_comment(cnv_id):
    """
    Un Hide CNV comment
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.cnv_handler.unhide_cnvs_comment(cnv_id, comment_id)
    return redirect(url_for("dna_bp.show_cnv", id=cnv_id))


###### TRANSLOCATIONS VIEW PAGE #######
@dna_bp.route("/transloc/<string:id>")
@login_required
def show_transloc(id):
    """
    Show Translocation view page
    """
    transloc = store.transloc_handler.get_transloc(id)
    sample = store.sample_handler.get_sample_with_id((transloc["SAMPLE_ID"]))
    assay = util.common.get_assay_from_sample(sample)
    sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    bam_id = store.bam_service_handler.get_bams(sample_ids)

    annotations = store.transloc_handler.get_transloc_annotations(transloc)
    return render_template(
        "show_transloc.html",
        tl=transloc,
        sample=sample,
        classification=999,
        annotations=annotations,
        bam_id=bam_id,
    )


@dna_bp.route("/transloc/interesttransloc/<string:id>", methods=["POST"])
@login_required
def mark_interesting_transloc(id):
    store.transloc_handler.mark_interesting_transloc(id)
    return redirect(url_for("dna_bp.show_transloc", id=id))


@dna_bp.route("/transloc/uninteresttransloc/<string:id>", methods=["POST"])
@login_required
def unmark_interesting_transloc(id):
    store.transloc_handler.unmark_interesting_transloc(id)
    return redirect(url_for("dna_bp.show_transloc", id=id))


@dna_bp.route("/transloc/fptransloc/<string:id>", methods=["POST"])
@login_required
def mark_false_transloc(id):
    store.transloc_handler.mark_false_positive_transloc(id)
    return redirect(url_for("dna_bp.show_transloc", id=id))


@dna_bp.route("/transloc/unfptransloc/<string:id>", methods=["POST"])
@login_required
def unmark_false_transloc(id):
    store.transloc_handler.unmark_false_positive_transloc(id)
    return redirect(url_for("dna_bp.show_transloc", id=id))


@dna_bp.route("/transloc/hide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def hide_transloc_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.transloc_handler.hide_transloc_comment(var_id, comment_id)
    return redirect(url_for("dna_bp.show_transloc", id=var_id))


@dna_bp.route("/transloc/unhide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def unhide_transloc_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.transloc_handler.unhide_transloc_comment(var_id, comment_id)
    return redirect(url_for("dna_bp.show_transloc", id=var_id))


##### PREVIEW REPORT ######
@dna_bp.route("/sample/preview_report/<string:id>", methods=["GET", "POST"])
@login_required
def generate_dna_report(id, *args, **kwargs):

    sample = store.sample_handler.get_sample(id)  # id = name

    if not sample:
        sample = store.sample_handler.get_sample_with_id(id)  # id = id

    assay = util.common.get_assay_from_sample(sample)
    subpanel = sample.get("subpanel")

    sample["num_samples"] = store.variant_handler.get_num_samples(str(sample["_id"]))

    ## send over all defined gene panels per assay, to matching template ##
    gene_lists, genelists_assay = store.panel_handler.get_assay_panels(assay)

    # TODO: Fix this function
    genelist_filter = sample.get("checked_genelists", {})

    ## remove genelist_ from each list
    genelist_filter_ = [sub.replace("genelist_", "") for sub in genelist_filter]

    ## displaynames for report
    genelist_dispnames = util.common.get_genelist_dispnames(genelists_assay, genelist_filter_)

    panels = [panel.get("name") for panel in genelists_assay]

    group = util.common.select_one_sample_group(sample.get("groups"))
    group_params = util.common.get_group_parameters(group)
    settings = util.common.get_group_defaults(group_params)

    ## get sample settings
    sample_settings = util.common.get_sample_settings(sample, settings)

    filter_conseq = util.dna.get_filter_conseq_terms(sample_settings.get("csq_filter", {}).keys())
    filter_genes = util.common.create_filter_genelist(genelist_filter, gene_lists)

    query = build_query(
        assay,
        {
            "id": str(sample["_id"]),
            "max_freq": sample_settings["max_freq"],
            "min_freq": sample_settings["min_freq"],
            "min_depth": sample_settings["min_depth"],
            "min_reads": sample_settings["min_reads"],
            "max_popfreq": sample_settings["max_popfreq"],
            "filter_conseq": filter_conseq,
        },
    )
    query["fp"] = {"$ne": True}
    query["irrelevant"] = {"$ne": True}
    variants_iter = store.variant_handler.get_case_variants(query)

    variants = list(variants_iter)

    # Add blacklist data
    variants = store.blacklist_handler.add_blacklist_data(variants, assay)

    variants = util.dna.add_global_annotations(variants, assay, subpanel)

    # Filter by population frequency
    variants = util.dna.popfreq_filter(variants, float(sample_settings["max_popfreq"]))

    # Add hotspot data
    variants = util.dna.hotspot_variant(variants)

    # Filter variants for report
    variants = util.dna.filter_variants_for_report(variants, filter_genes, assay)

    # Sample dict for the variant summary table in the report
    simple_variants = util.dna.get_simple_variants_for_report(variants)

    # TODO: LOW COV
    # LOWCOV data, very computationally intense for samples with many regions
    low_cov = {}
    # low_cov = store.coverage_handler.get_sample_coverage(sample["name"])
    # print(list(low_cov))

    ## GET CNVs TRANSLOCS and OTHER BIOMARKERS ## # TODO NEEDS TO BE TESTED
    cnvs_iter = False
    biomarkers_iter = False
    transloc_iter = False
    cnv_profile_base64 = None
    if group_params is not None and "DNA" in group_params:
        if group_params["DNA"].get("CNV"):
            cnvs_iter = list(
                store.cnv_handler.get_interesting_sample_cnvs(sample_id=str(sample["_id"]))
            )
            cnv_profile_base64 = util.common.get_plot(
                os.path.basename(sample.get("cnvprofile", "")), assay
            )
            # this line checks if the cnvs are empty, if they are, it sets the cnvs_iter to True for easy way in the report
            # this means that we need to show cnvs despite them being empty because the group demands for it
            if not cnvs_iter:
                cnvs_iter = True
        if group_params["DNA"].get("OTHER"):
            biomarkers_iter = store.biomarker_handler.get_sample_biomarkers(
                sample_id=str(sample["_id"])
            )
            if not biomarkers_iter:
                biomarkers_iter = True
        if group_params["DNA"].get("FUSIONS"):
            transloc_iter = store.transloc_handler.get_interesting_sample_translocations(
                sample_id=str(sample["_id"])
            )
            if not transloc_iter:
                transloc_iter = True

    # report header and date
    analysis_method = util.common.get_analysis_method(assay)
    report_header = util.common.get_report_header(assay, sample)
    report_date = datetime.now().date()
    save = kwargs.get("save", 0)
    template = "dna_report.html"

    return render_template(
        template,
        variants=variants,
        simple_variants=simple_variants,
        sample=sample,
        low_cov=low_cov,
        translation=app.config.get("REPORT_CONFIG").get("REPORT_TRANS"),
        group=sample["groups"],
        cnvs=cnvs_iter,  # cnvs_list, TMP
        cnv_profile_base64=cnv_profile_base64,
        translocs=list(transloc_iter),  # not gmsonco
        class_desc=app.config.get("REPORT_CONFIG").get("CLASS_DESC"),
        class_desc_short=app.config.get("REPORT_CONFIG").get("CLASS_DESC_SHORT"),
        report_date=report_date,
        dispgenes=filter_genes,
        save=save,
        assay=assay,
        biomarkers=biomarkers_iter,  # solid
        checked_genelists=genelist_dispnames,  # solid
        report_header=report_header,
        analysis_method=analysis_method,
        analysis_desc=app.config.get("REPORT_CONFIG").get("ANALYSIS_DESCRIPTION", {}).get(assay),
        gene_table=app.config.get("REPORT_CONFIG").get("GENE_TABLE", {}).get(assay),
        panel=group_params.get("panel_name", assay),
    )


@dna_bp.route("/sample/report/save/<string:id>")
@login_required
def save_dna_report(id):
    sample = store.sample_handler.get_sample(id)  # id = name

    if not sample:
        sample = store.sample_handler.get_sample_with_id(id)  # id = id

    assay = util.common.get_assay_from_sample(sample)

    # Get report number
    report_num = 1
    if "report_num" in sample:
        report_num = sample["report_num"] + 1

    # report file name
    report_path = f"{app.config['REPORTS_BASE_PATH']}/{assay}"
    report_file = f"{app.config['REPORTS_BASE_PATH']}/{id}_{str(report_num)}.html"
    # report_file = f"{app.config['REPORTS_BASE_PATH']}/test.html"

    if not os.path.exists(report_path):
        flash(f"Creating directory {report_path}", "yellow")
        os.makedirs(report_path)

    if util.common.check_report_exists(report_file):
        flash("Report already exists", "red")
        raise AppError(
            status_code=409,
            message="Report already exists with the requested name.",
            details=f"File name: {os.path.basename(report_file)}",
        )

    # Attempt to write the report to a file
    try:
        html = generate_dna_report(id, save=1)
        if not util.common.write_report(html, report_file):
            raise AppError(
                status_code=500,
                message=f"Failed to save report {id}_{report_num}.html",
                details="An issue occurred while writing the report to the file system.",
            )

        # Success case
        flash(f"Report id {id}_{report_num}.html is saved!", "green")

    except Exception as e:
        # Distinguish between AppError and generic exceptions
        if isinstance(e, AppError):
            # Handle the application-specific error
            flash(e.message, "red")
            app.logger.error(f"AppError: {e.message} | Details: {e.details}")
        else:
            # Handle unexpected errors
            flash("An unexpected error occurred. Please try again later.", "red")
            app.logger.exception(f"Unexpected error: {str(e)}")

    # TODO: Uncomment this
    # Add to database
    # app.config["SAMPLES_COLL"].update(
    #     {"name": id},
    #     {
    #         "$push": {
    #             "reports": {
    #                 "_id": ObjectId(),
    #                 "report_num": report_num,
    #                 "filepath": pdf_file,
    #                 "author": current_user.get_id(),
    #                 "time_created": datetime.now(),
    #             }
    #         },
    #         "$set": {"report_num": report_num},
    #     },
    # )

    return redirect(url_for("home_bp.home_screen"))
