"""
Coyote case variants
"""

from flask import abort
from flask import current_app as app
from flask import redirect, render_template, request, url_for, send_from_directory
from flask_login import current_user, login_required
from pprint import pformat

from coyote.blueprints.variants.forms import FilterForm
from wtforms import BooleanField
from wtforms.validators import Optional
from coyote.extensions import store
from coyote.blueprints.variants import variants_bp
from coyote.blueprints.variants.varqueries import build_query
from coyote.blueprints.variants import varqueries_notbad
from coyote.blueprints.variants import util
from coyote.blueprints.variants import filters


@variants_bp.route("/sample/<string:id>", methods=["GET", "POST"])
@login_required
def list_variants(id):

    # Find sample data by name
    sample = store.get_sample(id)
    sample_ids = store.get_sample_ids(str(sample["_id"]))
    smp_grp = sample["groups"][0]
    group = app.config["GROUP_CONFIGS"].get(smp_grp)
    settings = util.get_group_defaults(group)
    assay = util.get_assay_from_sample(sample)
    subpanel = sample.get("subpanel")

    app.logger.info(app.config["GROUP_CONFIGS"])  # get group config from app config instead
    app.logger.info(f"the sample has these groups {smp_grp}")
    app.logger.info(f"this is the group from collection {group}")
    # group = store.get_sample_groups( sample["groups"][0] ) # this is the old way of getting group config from mongodb

    ## GENEPANELS ##
    ## send over all defined gene panels per assay, to matching template ##
    gene_lists, genelists_assay = store.get_assay_panels(assay)
    ## Default gene list. For samples with default_genelis_set=1 add a gene list to specific subtypes lunga, hjärna etc etc. Will fetch genelist from mongo collection.
    # this only for assays that should have a default gene list. Will always be added to sample if not explicitely removed from form
    if "default_genelist_set" in group:
        if "subpanel" in sample:
            panel_genelist = store.get_panel(subpanel=sample["subpanel"], type="genelist")
            if panel_genelist:
                settings["default_checked_genelists"] = {"genelist_" + sample["subpanel"]: 1}

    # Save new filter settings if submitted
    # Inherit FilterForm, pass all genepanels from mongodb, set as boolean, NOW IT IS DYNAMIC!
    class GeneForm(FilterForm):
        pass

    for panel in genelists_assay:
        if panel["type"] == "genelist":
            setattr(GeneForm, "genelist_" + panel["name"], BooleanField())
    form = GeneForm()
    ###########################################################################

    ## FORM FILTERS ##
    # Either reset sample to default filters or add the new filters from form.
    if request.method == "POST" and form.validate_on_submit():
        # Reset filters to defaults
        if form.reset.data == True:
            store.reset_sample_settings(id, settings)
        # Change filters
        else:
            store.update_sample_settings(id, form)
        ## get sample again to recieve updated forms!
        sample = store.get_sample(id)
    ############################################################################

    # Check if sample has hidden comments
    has_hidden_comments = 0
    if "comments" in sample:
        for comm in sample["comments"]:
            if comm["hidden"] == 1:
                has_hidden_comments = 1

    ## get sample settings
    sample_settings = util.get_sample_settings(sample, settings)
    # sample filters, either set, or default
    cnv_effects = sample.get("checked_cnveffects", settings["default_checked_cnveffects"])
    genelist_filter = sample.get("checked_genelists", settings["default_checked_genelists"])
    filter_conseq = util.get_filter_conseq_terms(sample_settings["csq_filter"].keys())
    filter_genes = util.create_genelist(genelist_filter, gene_lists)
    filter_cnveffects = util.create_cnveffectlist(cnv_effects)

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
        group,
    )
    app.logger.info("this is the old varquery: %s", pformat(query))
    app.logger.info("this is the new varquery: %s", pformat(query2))
    variants_iter = store.get_case_variants(query)
    # Find all genes matching the query
    variants, genes = util.get_protein_coding_genes(variants_iter)
    # Add blacklist data, ADD ALL variants_iter via the store please...
    # util.add_blacklist_data( variants, assay )
    # Get canonical transcripts for the genes from database
    canonical_dict = store.get_canonical(list(genes.keys()))
    # Select a VEP consequence for each variant
    for var_idx, var in enumerate(variants):
        (
            variants[var_idx]["INFO"]["selected_CSQ"],
            variants[var_idx]["INFO"]["selected_CSQ_criteria"],
        ) = util.select_csq(var["INFO"]["CSQ"], canonical_dict)
        (
            variants[var_idx]["global_annotations"],
            variants[var_idx]["classification"],
            variants[var_idx]["other_classification"],
            variants[var_idx]["annotations_interesting"],
        ) = store.get_global_annotations(variants[var_idx], assay, subpanel)
    # Filter by population frequency
    variants = util.popfreq_filter(variants, float(sample_settings["max_popfreq"]))
    variants = util.hotspot_variant(variants)
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
    if group != None and "DNA" in group:
        if group["DNA"]["CNV"]:
            cnvwgs_iter = list(store.get_sample_cnvs(sample_id=str(sample["_id"])))
            if filter_cnveffects:
                cnvwgs_iter = util.cnvtype_variant(cnvwgs_iter, filter_cnveffects)
            cnvwgs_iter = util.cnv_organizegenes(cnvwgs_iter)
            cnvwgs_iter_n = list(store.get_sample_cnvs(sample_id=str(sample["_id"]), normal=True))
        if group["DNA"]["OTHER"]:
            biomarkers_iter = store.get_sample_other(sample_id=str(sample["_id"]))
        if group["DNA"]["FUSIONS"]:
            transloc_iter = store.get_sample_translocations(sample_id=str(sample["_id"]))
    #################################################

    ## "AI"-text depending on what analysis has been done. Add translocs and cnvs if marked as interesting (HRD and MSI?)
    ## SNVs, non-optional. Though only has rules for PARP + myeloid and solid
    ai_text = ""
    conclusion = ""
    # ai_text, conclusion = util.generate_ai_text( assay, variants, filter_genes, genelist_filter, sample["groups"][0] )
    ## translocations (DNA fusions) and copy number variation. Works for solid so far, should work for myeloid, lymphoid
    if assay == "solid":
        transloc_iter_ai = store.get_sample_translocations(sample_id=str(sample["_id"]))
        biomarkers_iter_ai = store.get_sample_other(sample_id=str(sample["_id"]))
        ai_text_transloc = util.generate_ai_text_nonsnv(
            assay, transloc_iter_ai, sample["groups"][0], "transloc"
        )
        ai_text_cnv = util.generate_ai_text_nonsnv(assay, cnvwgs_iter, sample["groups"][0], "cnv")
        ai_text_bio = util.generate_ai_text_nonsnv(
            assay, biomarkers_iter_ai, sample["groups"][0], "bio"
        )
        ai_text = ai_text + ai_text_transloc + ai_text_cnv + ai_text_bio + conclusion
    else:
        ai_text = ai_text + conclusion

    # this is in config, but needs to be tested (2024-05-14) with a HD-sample of relevant name
    disp_pos = []
    if "verif_samples" in group:
        if sample["name"] in group["verif_samples"]:
            disp_pos = group["verif_samples"][sample["name"]]
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


@app.route("/plot/<string:fn>/<string:assay>/<string:build>")
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


@app.route("/sample/sample_comment/<string:id>", methods=["POST"])
@login_required
def add_sample_comment(id):
    """
    rewrite to use app.store instead
    """
    # app.config['SAMPLES_COLL'].update(
    #     { '_id': ObjectId(id) },
    #     { "$push": { 'comments': { '_id':ObjectId(), 'hidden':0, 'text':request.form['sample_comment'], 'author':current_user.get_id(), 'time_created':datetime.now() }}} )
    return redirect(url_for("list_variants", id=id))


# TODO CHECK AGAIN AND MODIFY THE CODE AS PER THE REQUIREMENT
## Individual variant view ##
@app.route("/var/<string:id>")
@login_required
def show_variant(id):

    variant = store.get_variant(id)
    in_other = store.get_variant_in_other_samples(variant)
    sample = store.get_sample_with_id(variant["SAMPLE_ID"])

    assay = util.get_assay_from_sample(sample)
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
    has_hidden_comments = 0
    if "comments" in variant:
        for comm in variant["comments"]:
            if comm["hidden"] == 1:
                has_hidden_comments = 1

    expression = store.get_expression_data(list(transcripts.keys()))

    variant = store.add_blacklist_data([variant], assay)

    # Get canonical transcripts for all genes annotated for the variant
    canonical_dict = store.get_canonical(list(genes.keys()))

    # Select a transcript
    (variant["INFO"]["selected_CSQ"], variant["INFO"]["selected_CSQ_criteria"]) = util.select_csq(
        variant["INFO"]["CSQ"], canonical_dict
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

    civic = store.get_civic_data(variant, variant_desc)

    civic_gene = store.get_civic_gene(variant["INFO"]["selected_CSQ"]["SYMBOL"])

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

    oncokb = store.get_oncokb_anno(variant, oncokb_hgvsp)
    oncokb_action = store.get_oncokb_action(variant, oncokb_hgvsp)
    oncokb_gene = store.get_oncokb_gene(variant["INFO"]["selected_CSQ"]["SYMBOL"])

    # Find BRCA-exchange data
    brca_exchange = store.get_brca_exchange_data(variant, assay)

    # Find IARC TP53 data
    iarc_tp53 = store.find_iarc_tp53(variant)

    # Get bams
    sample_ids = store.get_sample_ids(str(sample["_id"]))
    bam_id = store.get_bams(sample_ids)

    # Format PON (panel of normals) data
    pon = util.format_pon(variant)

    # Get global annotations for the variant
    annotations, classification, other_classifications, annotations_interesting = (
        store.get_global_annotations(variant, assay, subpanel)
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


@app.route("/var/unfp/<string:id>", methods=["POST"])
@login_required
def unmark_false_variant(id):
    """
    Unmark False Positive status of a variant in the database
    """
    store.is_false_positive(id, False)

    return redirect(url_for("show_variant", id=id))


@app.route("/var/fp/<string:id>", methods=["POST"])
@login_required
def mark_false_variant(id):
    """
    Mark False Positive status of a variant in the database
    """
    store.is_false_positive(id, True)
    return redirect(url_for("show_variant", id=id))


@app.route("/var/uninterest/<string:id>", methods=["POST"])
@login_required
def unmark_interesting_variant(id):
    """
    Unmark interesting status of a variant in the database
    """
    store.is_interesting(id, False)

    return redirect(url_for("show_variant", id=id))


@app.route("/var/interest/<string:id>", methods=["POST"])
@login_required
def mark_interesting_variant(id):
    """
    Mark interesting status of a variant in the database
    """
    store.is_interesting(id, True)

    return redirect(url_for("show_variant", id=id))


@app.route("/var/unirrelevant/<string:id>", methods=["POST"])
@login_required
def unmark_irrelevant_variant(id):
    """
    Unmark irrelevant status of a variant in the database
    """
    store.is_irrelevant(id, False)

    return redirect(url_for("show_variant", id=id))


@app.route("/var/irrelevant/<string:id>", methods=["POST"])
@login_required
def mark_irrelevant_variant(id):
    """
    Mark irrelevant status of a variant in the database
    """
    store.is_irrelevant(id, True)

    return redirect(url_for("show_variant", id=id))


@app.route("/var/blacklist/<string:id>", methods=["POST"])
@login_required
def add_variant_to_blacklist(id):

    var = store.get_variant(id)
    sample = store.get_sample_with_id(var["SAMPLE_ID"])
    assay = util.get_assay_from_sample(sample)
    store.blacklist_variant(var, assay)

    return redirect(url_for("show_variant", id=id))


@app.route("/var/ordersanger/<string:id>", methods=["POST"])
@login_required
def order_sanger(id):
    variant = store.get_variant(id)
    variants, genes = util.get_protein_coding_genes([variant])
    var = variants[0]
    sample = store.get_sample_with_id(var["SAMPLE_ID"])
    canonical_dict = store.get_canonical(list(genes.keys()))

    var["INFO"]["selected_CSQ"], var["INFO"]["selected_CSQ_criteria"] = util.select_csq(
        var["INFO"]["CSQ"], canonical_dict
    )

    hg38_chr, hg38_pos = util.get_hg38_pos(str(var["CHROM"]), str(var["POS"]))
    ncbi_link = util.get_ncbi_link(hg38_chr, hg38_pos)
    thermo_link = util.get_thermo_link(hg38_chr, hg38_pos)

    gtcalls = util.get_gt_calls(var)

    html, tx_info = util.compose_sanger_email(
        var, sample["name"], gtcalls, hg38_chr, hg38_pos, ncbi_link, thermo_link
    )

    email_status = util.send_sanger_email(html, tx_info["SYMBOL"])

    return redirect(url_for("show_variant", id=id))


@app.route("/var/classify/<string:id>", methods=["POST"])
@login_required
def classify_variant(id):
    form_data = request.form.to_dict()
    class_num = util.get_tier_classification(form_data)

    nomenclature, variant = util.get_variant_nomenclature(form_data)
    if class_num != 0:
        store.insert_classified_variant(variant, nomenclature, class_num, form_data)

    if class_num != 0:
        if nomenclature == "f":
            return redirect(url_for("show_fusion", id=id))

    return redirect(url_for("show_variant", id=id))


@app.route("/var/rmclassify/<string:id>", methods=["POST"])
@login_required
def remove_classified_variant(id):
    form_data = request.form.to_dict()
    nomenclature, variant = util.get_variant_nomenclature(form_data)
    per_assay = store.delete_classified_variant(variant, nomenclature, form_data)
    app.logger.debug(per_assay)
    return redirect(url_for("show_variant", id=id))


@app.route("/var/comment/<string:id>", methods=["POST"])
@login_required
def add_variant_comment(id):
    """
    Add a comment to a variant
    """

    # If global checkbox. Save variant with the protein, coding och genomic nomenclature in decreasing priority
    form_data = request.form.to_dict()
    nomenclature, variant = util.get_variant_nomenclature(form_data)
    doc = util.create_var_comment_doc(nomenclature, variant, form_data)
    _type = form_data.get("global", None)
    util.insert_var_comment(
        id,
        nomenclature,
        doc,
        _type,
    )

    if nomenclature == "f":
        return redirect(url_for("show_fusion", id=id))
    elif nomenclature == "t":
        return redirect(url_for("show_transloc", id=id))
    elif nomenclature == "cn":
        return redirect(url_for("show_cnvwgs", id=id))

    return redirect(url_for("show_variant", id=id))


@app.route("/var/hide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def hide_variant_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.hide_var_comment(var_id, comment_id)
    return redirect(url_for("show_variant", id=var_id))


@app.route("/var/unhide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def unhide_variant_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.unhide_variant_comment(var_id, comment_id)
    return redirect(url_for("show_variant", id=var_id))


###### CNVS VIEW PAGE #######
@app.route("/cnvwgs/<string:id>")
@login_required
def show_cnvwgs(id):
    """
    Show CNVs view page
    """
    cnv = store.get_cnv(id)
    sample = store.get_sample_with_id((cnv["SAMPLE_ID"]))
    assay = util.get_assay_from_sample(sample)
    sample_ids = store.get_sample_ids(str(sample["_id"]))
    bam_id = store.get_bams(sample_ids)

    annotations = store.get_cnv_annotations(cnv)
    return render_template(
        "show_cnvwgs.html",
        cnv=cnv,
        sample=sample,
        classification=999,
        annotations=annotations,
        sample_ids=sample_ids,
        bam_id=bam_id,
    )


@app.route("/var/uninterestcnv/<string:id>", methods=["POST"])
@login_required
def unmark_interesting_cnv(id):
    """
    Unmark CNV as interesting
    """

    store.is_intresting_cnv(id, False)
    return redirect(url_for("show_cnvwgs", id=id))


@app.route("/var/interestcnv/<string:id>", methods=["POST"])
@login_required
def mark_interesting_cnv(id):
    """
    Mark CNV as interesting
    """
    store.is_intresting_cnv(id, True)
    return redirect(url_for("show_cnvwgs", id=id))


@app.route("/var/fpcnv/<string:id>", methods=["POST"])
@login_required
def mark_false_cnv(id):
    """
    Mark CNV as false positive
    """
    store.mark_false_positive_cnv(id, True)
    return redirect(url_for("show_cnvwgs", id=id))


@app.route("/var/unfpcnv/<string:id>", methods=["POST"])
@login_required
def unmark_false_cnv(id):
    """
    Unmark CNV as false positive
    """
    store.mark_false_positive_cnv(id, False)
    return redirect(url_for("show_cnvwgs", id=id))


@app.route("/cnvwgs/hide_variant_comment/<string:cnv_id>", methods=["POST"])
@login_required
def hide_cnv_comment(cnv_id):
    """
    Hide CNV comment
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.hide_cnvs_comment(cnv_id, comment_id)
    return redirect(url_for("show_cnvwgs", id=cnv_id))


@app.route("/cnvwgs/unhide_variant_comment/<string:cnv_id>", methods=["POST"])
@login_required
def unhide_cnv_comment(cnv_id):
    """
    Un Hide CNV comment
    """
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.unhide_cnvs_comment(cnv_id, comment_id)
    return redirect(url_for("show_cnvwgs", id=cnv_id))


###### TRANSLOCATIONS VIEW PAGE #######
@app.route("/transloc/<string:id>")
@login_required
def show_transloc(id):
    """
    Show Translocation view page
    """
    transloc = store.get_transloc(id)
    sample = store.get_sample_with_id((transloc["SAMPLE_ID"]))
    assay = util.get_assay_from_sample(sample)
    sample_ids = store.get_sample_ids(str(sample["_id"]))
    bam_id = store.get_bams(sample_ids)

    annotations = store.get_transloc_annotations(transloc)
    return render_template(
        "show_transloc.html",
        tl=transloc,
        sample=sample,
        classification=999,
        annotations=annotations,
        bam_id=bam_id,
    )


@app.route("/var/interesttransloc/<string:id>", methods=["POST"])
@login_required
def mark_interesting_transloc(id):
    store.is_intresting_transloc(id, True)
    return redirect(url_for("show_transloc", id=id))


@app.route("/var/uninteresttransloc/<string:id>", methods=["POST"])
@login_required
def unmark_interesting_transloc(id):
    store.is_intresting_transloc(id, False)
    return redirect(url_for("show_transloc", id=id))


@app.route("/var/fptransloc/<string:id>", methods=["POST"])
@login_required
def mark_false_transloc(id):
    store.mark_false_positive_transloc(id, True)
    return redirect(url_for("show_transloc", id=id))


@app.route("/var/unfptransloc/<string:id>", methods=["POST"])
@login_required
def unmark_false_transloc(id):
    store.mark_false_positive_transloc(id, False)
    return redirect(url_for("show_transloc", id=id))


@app.route("/tl/hide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def hide_transloc_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.hide_transloc_comment(var_id, comment_id, store.transloc_collection)
    return redirect(url_for("show_transloc", id=var_id))


@app.route("/tl/unhide_variant_comment/<string:var_id>", methods=["POST"])
@login_required
def unhide_transloc_comment(var_id):
    comment_id = request.form.get("comment_id", "MISSING_ID")
    store.unhide_transloc_comment(var_id, comment_id, store.transloc_collection)
    return redirect(url_for("show_transloc", id=var_id))
