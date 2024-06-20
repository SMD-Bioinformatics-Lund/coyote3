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

@variants_bp.route('/dna/sample/<string:id>', methods=['GET', 'POST'])
@login_required
def list_variants(id):

    # Find sample data by name
    sample     = store.get_sample(id)
    sample_ids = store.get_sample_ids(str(sample["_id"]))
    smp_grp    = sample["groups"][0]
    group      = app.config["GROUP_CONFIGS"].get( smp_grp )
    settings   = util.get_group_defaults( group )
    assay      = util.get_assay_from_sample( sample )
    subpanel   = sample.get('subpanel')
    

    app.logger.info(app.config["GROUP_CONFIGS"]) # get group config from app config instead
    app.logger.info(f"the sample has these groups {smp_grp}")
    app.logger.info(f"this is the group from collection {group}")
    #group = store.get_sample_groups( sample["groups"][0] ) # this is the old way of getting group config from mongodb

    ## GENEPANELS ##
    ## send over all defined gene panels per assay, to matching template ##
    gene_lists, genelists_assay = store.get_assay_panels(assay)
    
    app.logger.info(f"this is the gene_lists, genelists_assay {gene_lists},{genelists_assay}")
    ## Default gene list. For samples with default_genelis_set=1 add a gene list to specific subtypes lunga, hjärna etc etc. Will fetch genelist from mongo collection. 
    # this only for assays that should have a default gene list. Will always be added to sample if not explicitely removed from form
    if "default_genelist_set" in group:
        if "subpanel" in sample:
            panel_genelist = store.get_panel( subpanel=sample['subpanel'], type='genelist')
            if panel_genelist:
                settings["default_checked_genelists"] = { "genelist_"+sample['subpanel']:1 }
    # Save new filter settings if submitted
    # Inherit FilterForm, pass all genepanels from mongodb, set as boolean, NOW IT IS DYNAMIC!
    class GeneForm(FilterForm):
        pass
    for panel in genelists_assay:
        if panel['type'] == 'genelist':
            setattr(GeneForm, "genelist_"+panel['name'], BooleanField())
    form = GeneForm()
    ###########################################################################

    ## FORM FILTERS ##
    # Either reset sample to default filters or add the new filters from form.
    if request.method == 'POST' and form.validate_on_submit():
        # Reset filters to defaults
        if form.reset.data == True:
            store.reset_sample_settings(id,settings)
        # Change filters
        else:
            store.update_sample_settings(id,form)
        ## get sample again to recieve updated forms!
        sample = store.get_sample(id) 
    ############################################################################
        
    # Check if sample has hidden comments
    has_hidden_comments = 0
    if 'comments' in sample:
        for comm in sample["comments"]:
            if comm["hidden"] == 1:
                has_hidden_comments = 1      
  
    ## get sample settings
    sample_settings         = util.get_sample_settings(sample,settings)
    # sample filters, either set, or default 
    cnv_effects             = sample.get("checked_cnveffects", settings["default_checked_cnveffects"])
    genelist_filter         = sample.get("checked_genelists", settings["default_checked_genelists"])
    filter_conseq           = util.get_filter_conseq_terms( sample_settings["csq_filter"].keys() )
    filter_genes            = util.create_genelist( genelist_filter, gene_lists )
    filter_cnveffects       = util.create_cnveffectlist( cnv_effects )

    # Add them to the form
    form.min_freq.data      = sample_settings["min_freq"]
    form.max_freq.data      = sample_settings["max_freq"]
    form.min_depth.data     = sample_settings["min_depth"]
    form.min_reads.data     = sample_settings["min_reads"]
    form.max_popfreq.data   = sample_settings["max_popfreq"]
    form.min_cnv_size.data  = sample_settings["min_cnv_size"]
    form.max_cnv_size.data  = sample_settings["max_cnv_size"]
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
        group
    )
    app.logger.info("this is the old varquery: %s", pformat(query))
    app.logger.info("this is the new varquery: %s", pformat(query2))
    variants_iter = store.get_case_variants( query )
    # Find all genes matching the query
    variants, genes = util.get_protein_coding_genes( variants_iter )
    # Add blacklist data, ADD ALL variants_iter via the store please...
    #util.add_blacklist_data( variants, assay )
    # Get canonical transcripts for the genes from database
    canonical_dict = store.get_canonical( list(genes.keys()) )
    # Select a VEP consequence for each variant
    for var_idx, var in enumerate(variants):
        variants[var_idx]["INFO"]["selected_CSQ"], variants[var_idx]["INFO"]["selected_CSQ_criteria"] = util.select_csq( var["INFO"]["CSQ"], canonical_dict )
        variants[var_idx]["global_annotations"], variants[var_idx]["classification"], variants[var_idx]["other_classification"], variants[var_idx]["annotations_interesting"] = store.get_global_annotations( variants[var_idx], assay, subpanel ) 
    # Filter by population frequency
    variants = util.popfreq_filter( variants, float(sample_settings["max_popfreq"]) )
    variants = util.hotspot_variant(variants)
    ### SNV FILTRATION ENDS HERE ###

    # LOWCOV data, very computationally intense for samples with many regions
    low_cov = {}
    #low_cov = app.config['COV_COLL'].find( { 'sample': id } )
    ## add cosmic to lowcov regions. Too many lowcov regions and this becomes very slow
    # this could maybe be something else than cosmic? config important regions?
    #if assay != "solid":
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
                cnvwgs_iter = util.cnvtype_variant(cnvwgs_iter, filter_cnveffects )
            cnvwgs_iter = util.cnv_organizegenes( cnvwgs_iter )
            cnvwgs_iter_n = list(store.get_sample_cnvs(sample_id=str(sample["_id"]),normal=True))
        if group["DNA"]["OTHER"]:
            biomarkers_iter = store.get_sample_other( sample_id=str(sample["_id"] ))
        if group["DNA"]["FUSIONS"]:
            transloc_iter = store.get_sample_translocations( sample_id=str(sample["_id"] ))
    #################################################

    ## "AI"-text depending on what analysis has been done. Add translocs and cnvs if marked as interesting (HRD and MSI?)
    ## SNVs, non-optional. Though only has rules for PARP + myeloid and solid
    ai_text = ""
    conclusion = ""
    #ai_text, conclusion = util.generate_ai_text( assay, variants, filter_genes, genelist_filter, sample["groups"][0] )
    ## translocations (DNA fusions) and copy number variation. Works for solid so far, should work for myeloid, lymphoid
    if (assay == "solid" ):
        transloc_iter_ai   = store.get_sample_translocations( sample_id=str(sample["_id"] ))
        biomarkers_iter_ai = store.get_sample_other( sample_id=str(sample["_id"] ))
        ai_text_transloc   = util.generate_ai_text_nonsnv( assay, transloc_iter_ai, sample["groups"][0], "transloc" )
        ai_text_cnv        = util.generate_ai_text_nonsnv( assay, cnvwgs_iter, sample["groups"][0], "cnv" )
        ai_text_bio        = util.generate_ai_text_nonsnv( assay, biomarkers_iter_ai, sample["groups"][0], "bio" )
        ai_text            = ai_text+ai_text_transloc+ai_text_cnv+ai_text_bio+conclusion
    else:
        ai_text = ai_text + conclusion

    # this is in config, but needs to be tested (2024-05-14) with a HD-sample of relevant name
    disp_pos = []
    if "verif_samples" in group:
        if sample["name"] in group["verif_samples"]:
            disp_pos = group["verif_samples"][sample["name"]]
    # this is to allow old samples to view plots, cnv + cnvprofile clash. Old assays used cnv as the entry for the plot, newer assays use cnv for path to cnv-file that was loaded.
    if "cnv" in sample:
        if sample["cnv"].lower().endswith(('.png', '.jpg', '.jpeg')):
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


@app.route('/plot/<string:fn>/<string:assay>/<string:build>')
def show_any_plot(fn,assay,build):
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
    

@app.route('/sample/sample_comment/<string:id>', methods=['POST'])
@login_required
def add_sample_comment(id):
    """
    rewrite to use app.store instead
    """
    # app.config['SAMPLES_COLL'].update(
    #     { '_id': ObjectId(id) },
    #     { "$push": { 'comments': { '_id':ObjectId(), 'hidden':0, 'text':request.form['sample_comment'], 'author':current_user.get_id(), 'time_created':datetime.now() }}} )
    return redirect(url_for('list_variants', id=id))