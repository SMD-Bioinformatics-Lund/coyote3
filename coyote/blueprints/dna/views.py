"""
Coyote case variants
"""

from flask import abort
from flask import current_app as app
from flask import redirect, render_template, request, url_for, send_from_directory, flash
from flask_login import current_user, login_required
from pprint import pformat
from coyote.blueprints.dna.forms import FilterForm, GeneForm
from wtforms import BooleanField
from wtforms.validators import Optional
from coyote.extensions import store
from coyote.blueprints.dna import dna_bp
from coyote.blueprints.dna.varqueries import build_query
from coyote.blueprints.dna import varqueries_notbad
from coyote.blueprints.dna import filters
from coyote.extensions import util
import logging


@dna_bp.route("/sample/<string:id>", methods=["GET", "POST"])
@login_required
def list_variants(id):

    # Find sample data by name
    sample = store.sample_handler.get_sample(id)  # id = name
    app.logger.debug(sample.get("_id"))
    app.logger.info(sample.get("_id"))
    app.logger.error(sample.get("_id"))
    app.logger.warning(sample.get("_id"))
    app.logger.critical(sample.get("_id"))

    # Get sample data by id if name is none
    if sample is None:
        sample = store.sample_handler.get_sample_with_id(id)  # id = id

    sample_ids = store.variant_handler.get_sample_ids(str(sample["_id"]))
    ## Check the leght of the sample groups from db, and if len is more than one, tumwgs-solid or tumwgs-hema takes the priority in new coyote
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
    subpanel = sample.get("subpanel")

    app.logger.debug(app.config["GROUP_CONFIGS"])  # get group config from app config instead
    app.logger.debug(f"the sample has these groups {smp_grp}")
    app.logger.debug(f"this is the group from collection {group_params}")
    # group = store.group_handler.get_sample_groups( sample["groups"][0] ) # this is the old way of getting group config from mongodb

    ## GENEPANELS ##
    ## send over all defined gene panels per assay, to matching template ##
    gene_lists, genelists_assay = store.panel_handler.get_assay_panels(assay)
    ## Default gene list. For samples with default_genelis_set=1 add a gene list to specific subtypes lunga, hjärna etc etc. Will fetch genelist from mongo collection.
    # this only for assays that should have a default gene list. Will always be added to sample if not explicitely removed from form
    if "default_genelist_set" in group_params:
        if "subpanel" in sample:
            panel_genelist = store.panel_handler.get_panel(
                subpanel=sample["subpanel"], type="genelist"
            )
            if panel_genelist:
                settings["default_checked_genelists"] = {f"genelist_{sample['subpanel']}": 1}

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
    filter_genes = util.common.create_genelist(genelist_filter, gene_lists)
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
    app.logger.debug("this is the new varquery: %s", pformat(query2))
    variants_iter = store.variant_handler.get_case_variants(query)
    # Find all genes matching the query
    variants, genes = store.variant_handler.get_protein_coding_genes(variants_iter)
    # Add blacklist data, ADD ALL variants_iter via the store please...
    # util.add_blacklist_data( variants, assay )
    # Get canonical transcripts for the genes from database
    canonical_dict = store.canonical_handler.get_canonical_by_genes(list(genes.keys()))
    # Select a VEP consequence for each variant
    for var_idx, var in enumerate(variants):
        (
            variants[var_idx]["INFO"]["selected_CSQ"],
            variants[var_idx]["INFO"]["selected_CSQ_criteria"],
        ) = util.dna.select_csq(var["INFO"]["CSQ"], canonical_dict)
        (
            variants[var_idx]["global_annotations"],
            variants[var_idx]["classification"],
            variants[var_idx]["other_classification"],
            variants[var_idx]["annotations_interesting"],
        ) = store.annotation_handler.get_global_annotations(variants[var_idx], assay, subpanel)
    # Filter by population frequency
    variants = util.dna.popfreq_filter(variants, float(sample_settings["max_popfreq"]))
    variants = store.variant_handler.hotspot_variant(variants)
    ### SNV FILTRATION ENDS HERE ###

    # LOWCOV data, very computationally intense for samples with many regions
    low_cov = {}
    # low_cov = app.config['COV_COLL'].find( { 'sample': id } )
    ## add cosmic to lowcov regions. Too many lowcov regions and this becomes very slow
    # this could maybe be something else than cosmic? config important regions?
    # if assay != "solid":
    #    low_cov = cosmic_variants_in_regions( low_cov )

    ## GET CNVs TRANSLOCS and OTHER BIOMARKERS ##
    cnvwgs_iter = False
    cnvwgs_iter_n = False
    biomarkers_iter = False
    transloc_iter = False
    if group_params != None and "DNA" in group_params:
        if group_params["DNA"].get("CNV"):
            cnvwgs_iter = list(store.cnv_handler.get_sample_cnvs(sample_id=str(sample["_id"])))
            if filter_cnveffects:
                cnvwgs_iter = store.cnv_handler.cnvtype_variant(cnvwgs_iter, filter_cnveffects)
            cnvwgs_iter = store.cnv_handler.cnv_organizegenes(cnvwgs_iter)
            cnvwgs_iter_n = list(
                store.cnv_handler.get_sample_cnvs(sample_id=str(sample["_id"]), normal=True)
            )
        if group_params["DNA"].get("OTHER"):
            biomarkers_iter = store.biomarker_handler.get_sample_other(sample_id=str(sample["_id"]))
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
        biomarkers_iter_ai = store.biomarker_handler.get_sample_other(sample_id=str(sample["_id"]))
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


@app.route("/plot/<string:fn>/<string:assay>/<string:build>")  # type: ignore
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

    cosm_ids = {}
    rs_ids = {}
    genes = {}
    transcripts = {}

    # Parse variation IDs and get all gene names
    for csq in variant["INFO"]["CSQ"]:
        ev_ids = csq["Existing_variation"].split("&")
        for ev_id in ev_ids:
            if ev_id.startswith("COSM"):
                cosm_ids[ev_id] = 1
            if ev_id.startswith("rs"):
                rs_ids[ev_id] = 1

        if csq["BIOTYPE"] == "protein_coding":
            genes[csq["SYMBOL"]] = 1
            transcripts[csq["Feature"]] = 1

    variant["INFO"]["rs_ids"] = rs_ids.keys()
    variant["INFO"]["cosm_ids"] = cosm_ids.keys()

    # Check if variant has hidden comments
    has_hidden_comments = store.variant_handler.hidden_var_comments(id)
    # has_hidden_comments = 0
    # if "comments" in variant:
    #     for comm in variant["comments"]:
    #         if comm["hidden"] == 1:
    #             has_hidden_comments = 1

    expression = store.expression_handler.get_expression_data(list(transcripts.keys()))

    variant = store.blacklist_handler.add_blacklist_data([variant], assay)

    # Get canonical transcripts for all genes annotated for the variant
    canonical_dict = store.canonical_handler.get_canonical_by_genes(list(genes.keys()))

    # Select a transcript
    (variant["INFO"]["selected_CSQ"], variant["INFO"]["selected_CSQ_criteria"]) = (
        util.dna.select_csq(variant["INFO"]["CSQ"], canonical_dict)
    )

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
        hgvsp = filters.one_letter_p(variant["INFO"]["selected_CSQ"]["HGVSp"]).split(":")[1]
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
    return redirect(url_for("show_variant", id=id))


@dna_bp.route("/var/fp/<string:id>", methods=["POST"])
@login_required
def mark_false_variant(id):
    """
    Mark False Positive status of a variant in the database
    """
    store.variant_handler.mark_false_positive_var(id)
    return redirect(url_for("show_variant", id=id))


@dna_bp.route("/var/uninterest/<string:id>", methods=["POST"])
@login_required
def unmark_interesting_variant(id):
    """
    Unmark interesting status of a variant in the database
    """
    store.variant_handler.unmark_interesting_var(id)
    return redirect(url_for("show_variant", id=id))


@dna_bp.route("/var/interest/<string:id>", methods=["POST"])
@login_required
def mark_interesting_variant(id):
    """
    Mark interesting status of a variant in the database
    """
    store.variant_handler.mark_interesting_var(id)
    return redirect(url_for("show_variant", id=id))


@dna_bp.route("/var/unirrelevant/<string:id>", methods=["POST"])
@login_required
def unmark_irrelevant_variant(id):
    """
    Unmark irrelevant status of a variant in the database
    """
    store.variant_handler.unmark_irrelevant_var(id)
    return redirect(url_for("show_variant", id=id))


@dna_bp.route("/var/irrelevant/<string:id>", methods=["POST"])
@login_required
def mark_irrelevant_variant(id):
    """
    Mark irrelevant status of a variant in the database
    """
    store.variant_handler.mark_irrelevant_var(id)
    return redirect(url_for("show_variant", id=id))


@dna_bp.route("/var/blacklist/<string:id>", methods=["POST"])
@login_required
def add_variant_to_blacklist(id):

    var = store.variant_handler.get_variant(id)
    sample = store.sample_handler.get_sample_with_id(var["SAMPLE_ID"])
    assay = util.common.get_assay_from_sample(sample)
    store.blacklist_handler.blacklist_variant(var, assay)

    return redirect(url_for("show_variant", id=id))


@dna_bp.route("/var/ordersanger/<string:id>", methods=["POST"])
@login_required
def order_sanger(id):
    variant = store.variant_handler.get_variant(id)
    variants, genes = store.variant_handler.get_protein_coding_genes([variant])
    var = variants[0]
    sample = store.sample_handler.get_sample_with_id(var["SAMPLE_ID"])
    canonical_dict = store.canonical_handler.get_canonical_by_genes(list(genes.keys()))

    var["INFO"]["selected_CSQ"], var["INFO"]["selected_CSQ_criteria"] = util.select_csq(
        var["INFO"]["CSQ"], canonical_dict
    )

    html, tx_info = util.dna.compose_sanger_email(var, sample["name"])

    email_status = util.dna.send_sanger_email(html, tx_info["SYMBOL"])

    return redirect(url_for("show_variant", id=id))


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

    return redirect(url_for("show_variant", id=id))


@dna_bp.route("/var/rmclassify/<string:id>", methods=["POST"])
@login_required
def remove_classified_variant(id):
    form_data = request.form.to_dict()
    nomenclature, variant = util.dna.get_variant_nomenclature(form_data)
    if nomenclature == "f":
        return redirect(url_for("rna_bp.show_fusion", id=id))
    per_assay = store.annotation_handler.delete_classified_variant(variant, nomenclature, form_data)
    app.logger.debug(per_assay)
    return redirect(url_for("show_variant", id=id))


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

    if nomenclature == "f":
        if _type != "global":
            store.fusion_handler.add_fusion_comment(id, doc)
        return redirect(url_for("rna_bp.show_fusion", id=id))
    elif nomenclature == "t":
        if _type != "global":
            store.transloc_handler.add_transloc_comment(id, doc)
        return redirect(url_for("show_transloc", id=id))
    elif nomenclature == "cn":
        if _type != "global":
            store.cnv_handler.add_cnv_comment(id, doc)
        return redirect(url_for("show_cnvwgs", id=id))
    else:
        if _type != "global":
            store.variant_handler.add_var_comment(id, doc)

    return redirect(url_for("show_variant", id=id))


@dna_bp.route("/var/hide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def hide_variant_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.variant_handler.hide_var_comment(var_id, comment_id)
    return redirect(url_for("show_variant", id=var_id))


@dna_bp.route("/var/unhide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def unhide_variant_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.variant_handler.unhide_variant_comment(var_id, comment_id)
    return redirect(url_for("show_variant", id=var_id))


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
    return redirect(url_for("show_cnvwgs", id=id))


@dna_bp.route("/cnv/interestcnv/<string:id>", methods=["POST"])
@login_required
def mark_interesting_cnv(id):
    """
    Mark CNV as interesting
    """
    store.cnv_handler.mark_interesting_cnv(id)
    return redirect(url_for("show_cnvwgs", id=id))


@dna_bp.route("/cnv/fpcnv/<string:id>", methods=["POST"])
@login_required
def mark_false_cnv(id):
    """
    Mark CNV as false positive
    """
    store.cnv_handler.mark_false_positive_cnv(id)
    return redirect(url_for("show_cnvwgs", id=id))


@dna_bp.route("/cnv/unfpcnv/<string:id>", methods=["POST"])
@login_required
def unmark_false_cnv(id):
    """
    Unmark CNV as false positive
    """
    store.cnv_handler.unmark_false_positive_cnv(id)
    return redirect(url_for("show_cnvwgs", id=id))


@dna_bp.route("/cnv/hide_variant_comment/<string:cnv_id>", methods=["POST"])
@login_required
def hide_cnv_comment(cnv_id):
    """
    Hide CNV comment
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.cnv_handler.hide_cnvs_comment(cnv_id, comment_id)
    return redirect(url_for("show_cnvwgs", id=cnv_id))


@dna_bp.route("/cnv/unhide_variant_comment/<string:cnv_id>", methods=["POST"])
@login_required
def unhide_cnv_comment(cnv_id):
    """
    Un Hide CNV comment
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.cnv_handler.unhide_cnvs_comment(cnv_id, comment_id)
    return redirect(url_for("show_cnvwgs", id=cnv_id))


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
    return redirect(url_for("show_transloc", id=id))


@dna_bp.route("/transloc/uninteresttransloc/<string:id>", methods=["POST"])
@login_required
def unmark_interesting_transloc(id):
    store.transloc_handler.unmark_interesting_transloc(id)
    return redirect(url_for("show_transloc", id=id))


@dna_bp.route("/transloc/fptransloc/<string:id>", methods=["POST"])
@login_required
def mark_false_transloc(id):
    store.transloc_handler.mark_false_positive_transloc(id)
    return redirect(url_for("show_transloc", id=id))


@dna_bp.route("/transloc/unfptransloc/<string:id>", methods=["POST"])
@login_required
def unmark_false_transloc(id):
    store.transloc_handler.unmark_false_positive_transloc(id)
    return redirect(url_for("show_transloc", id=id))


@dna_bp.route("/transloc/hide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def hide_transloc_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.transloc_handler.hide_transloc_comment(var_id, comment_id)
    return redirect(url_for("show_transloc", id=var_id))


@dna_bp.route("/transloc/unhide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def unhide_transloc_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.transloc_handler.unhide_transloc_comment(var_id, comment_id)
    return redirect(url_for("show_transloc", id=var_id))


###### FUSIONS VIEW PAGE #######
@dna_bp.route("/fusion/<string:id>")
@login_required
def show_fusion(id):
    """
    Show Fusion view page
    """
    pass
