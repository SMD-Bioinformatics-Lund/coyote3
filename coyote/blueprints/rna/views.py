"""
Coyote case variants
"""

from flask import abort
from flask import current_app as app
from flask import redirect, render_template, request, url_for, send_from_directory
from flask_login import current_user, login_required

from coyote.blueprints.variants.forms import FilterForm
from wtforms import BooleanField
from wtforms.validators import Optional
from coyote.extensions import store
from coyote.blueprints.variants import variants_bp
from coyote.blueprints.variants.varqueries import build_query
from coyote.blueprints.variants import util
from coyote.blueprints.variants import filters

@variants_bp.route('/sample/<string:id>', methods=['GET', 'POST'])
@login_required
def list_variants(id):
           
    # Find sample data by name
    sample = store.get_sample(id)     
    group = store.get_sample_groups( sample["groups"][0] )
    settings = util.get_group_defaults(group)
    assay = util.get_assay_from_sample( sample )
    subpanel = sample.get('subpanel')
    ## send over all defined gene panels per assay, to matching template ##
    genelists_assay = store.get_assay_panels(assay)
    ## fetch genepanel definitions from mongodb collection, TODO FIX FOR FUSIONS
    gene_lists = {}
    fusion_lists = {}
    panels = []
    for panel in genelists_assay:
        if panel['type'] == 'genelist':
            gene_lists[panel['name']] = panel['genes']
        elif panel['type'] == 'fusionlist':
            fusion_lists[panel['name']] = panel['genes']
        panels.append(panel['name'])
        
    ## Default gene list. For solid samples add a gene list to specific subtypes lunga, hjärna etc etc. Will fetch genelist from mongo collection. 
    # this only for assays that should have a default gene list. Will always be added to sample if not explicitely removed from form
    if assay == "solid":
        if ("subpanel" in sample):
            panel_genelist = app.config['PANELS_COLL'].find_one( { 'name':sample['subpanel'], 'type': 'genelist' } )
            panel_fusionlist = app.config['PANELS_COLL'].find_one( { 'name':sample['subpanel'], 'type': 'fusionlist' } )
            if panel_genelist:
                settings["default_checked_genelists"] = { "genelist_"+sample['subpanel']:1 }
            if panel_fusionlist:
                settings["default_checked_fusionlists"] = { "fusionlist_"+sample['subpanel']:1 }
    # Save new filter settings if submitted
    # Inherit FilterForm, pass all genepanels from mongodb, set as boolean, NOW IT IS DYNAMIC!
    class GeneForm(FilterForm):
        pass

    for panel in genelists_assay:
        if panel['type'] == 'genelist':
            setattr(GeneForm, "genelist_"+panel['name'], BooleanField())
        elif panel['type'] == 'fusionlist':
            setattr(GeneForm, "fusionlist_"+panel['name'], BooleanField(validators=[Optional()]))

    form = GeneForm()

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
        
    # Check if sample has hidden comments
    has_hidden_comments = 0
    if 'comments' in sample:
        for comm in sample["comments"]:
            if comm["hidden"] == 1:
                has_hidden_comments = 1        
    ## get sample settings
    sample_settings = util.get_sample_settings(sample,settings)
    # adjust filters from form. 
    cnv_effects          = sample.get("checked_cnveffects", settings["default_checked_cnveffects"])
    genelist_filter      = sample.get("checked_genelists", settings["default_checked_genelists"])
    fusionlist_filter    = sample.get("checked_fusionlists", settings["default_checked_fusionlists"])
    fusioneffect_filter  = sample.get("checked_fusioneffects", settings["default_checked_fusioneffects"])
    fusioncaller_filter  = sample.get("checked_fusioncallers", settings["default_checked_fusioncallers"])

    filter_conseq        = util. get_filter_conseq_terms( sample_settings["csq_filter"].keys() )
    filter_genes         = util.create_genelist( genelist_filter, gene_lists )
    filter_fusions       = util.create_fusiongenelist( fusionlist_filter, fusion_lists )
    filter_fusioneffects = util.create_fusioneffectlist( fusioneffect_filter )
    filter_callers       = util.create_fusioncallers ( fusioncaller_filter )
    filter_cnveffects    = util.create_cnveffectlist( cnv_effects )

    # Add them to the form
    form.min_freq.data = sample_settings["min_freq"]
    form.max_freq.data = sample_settings["max_freq"]
    form.min_depth.data = sample_settings["min_depth"]
    form.min_reads.data = sample_settings["min_reads"]
    form.max_popfreq.data = sample_settings["max_popfreq"]
    form.min_spanreads.data = sample_settings["min_spanreads"]
    form.min_spanpairs.data = sample_settings["min_spanpairs"]
    form.min_cnv_size.data = sample_settings["min_cnv_size"]
    form.max_cnv_size.data = sample_settings["max_cnv_size"]
   
    # should fusions have their own list_variants? perhaps move into separate blueprint
    # Find fusions
    fusions = []
    if assay == "fusion" or assay == "fusionrna":
        fusion_query = {"SAMPLE_ID": str(sample["_id"]), 'calls': { '$elemMatch': {'spanreads': {'$gte': int(sample_settings["min_spanreads"])}, 'spanpairs': {'$gte': int(sample_settings["min_spanpairs"])} } } }

        if filter_fusions:
            fusion_query['$or'] = [ {"gene1": { '$in':filter_fusions }}, {"gene2": { '$in':filter_fusions }} ]
        if filter_fusioneffects:
            fusion_query['calls.effect'] = {'$in': filter_fusioneffects }
        if "fusionlist_FCknown" in fusionlist_filter:
            fusion_query['calls.desc'] = {'$regex': 'known'}
        if "fusionlist_mitelman" in fusionlist_filter:
            fusion_query['calls.desc'] = {'$regex': 'mitelman'}
        if filter_callers:
            fusion_query['calls.caller'] = {'$in' : filter_callers}

        fusions = list(app.config['FUS_COLL'].find( fusion_query ))
        for fus_idx, fus in enumerate(fusions):
            fusions[fus_idx]["global_annotations"], fusions[fus_idx]["classification"] = get_fusion_annotations( fusions[fus_idx] ) # How slow is this????

    sample_ids = store.get_sample_ids(str(sample["_id"]))

    ## The query should really be constructed according to some configed rules for a specific assay
    query = build_query( assay, {"id":str(sample["_id"]), "max_freq":sample_settings["max_freq"], "min_freq":sample_settings["min_freq"], "min_depth":sample_settings["min_depth"], "min_reads":sample_settings["min_reads"], "max_popfreq":sample_settings["max_popfreq"], "filter_conseq":filter_conseq} )
    variants_iter = store.get_case_variants( query )
    ## SNV FILTRATION STARTS HERE ! ##
    ##################################  
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
    # get low cov data
    low_cov = {}
    #low_cov = app.config['COV_COLL'].find( { 'sample': id } )
    ## add cosmic to lowcov regions. Too many lowcov regions and this becomes very slow
    #if assay != "solid":
    #    low_cov = cosmic_variants_in_regions( low_cov )
    cnvwgs_iter = False
    cnvwgs_iter_n = False
    biomarkers_iter = False
    transloc_iter = False
    if group == None:
        group = {}
    if "DNA" in group:
        if group["DNA"]["CNV"]:
            cnvwgs_iter = list(app.config['CNVWGS_COLL'].find( { "SAMPLE_ID":str(sample["_id"]), 'NORMAL':{ '$exists': False } } ))
            if filter_cnveffects:
                cnvwgs_iter = cnvtype_variant(cnvwgs_iter, filter_cnveffects )
            cnvwgs_iter = cnv_organizegenes( cnvwgs_iter )
            cnvwgs_iter_n = list(app.config['CNVWGS_COLL'].find( { "SAMPLE_ID":str(sample["_id"]), 'NORMAL':{ '$exists': True } } ))
        if group["DNA"]["OTHER"]:
            biomarkers_iter = app.config['BIOMARKERS_COLL'].find( { "SAMPLE_ID":str(sample["_id"])} )
        if group["DNA"]["FUSIONS"]:
            transloc_iter = app.config['TRANSLOC_COLL'].find( { "SAMPLE_ID":str(sample["_id"])} )

    ## "AI"-text depending on what analysis has been done. Add translocs and cnvs if marked as interesting (HRD and MSI?)
    ## SNVs, non-optional. Though only has rules for PARP + myeloid and solid
    ai_text = ""
    conclusion = ""
    #ai_text, conclusion = util.generate_ai_text( assay, variants, filter_genes, genelist_filter, sample["groups"][0] )
    ## translocations (DNA fusions) and copy number variation. Works for solid so far, should work for myeloid, lymphoid
    if (assay == "solid" ):
        transloc_iter_ai = app.config['TRANSLOC_COLL'].find( { "SAMPLE_ID":str(sample["_id"])} )
        biomarkers_iter_ai = app.config['BIOMARKERS_COLL'].find( { "SAMPLE_ID":str(sample["_id"])} )
        ai_text_transloc = generate_ai_text_nonsnv( assay, transloc_iter_ai, sample["groups"][0], "transloc" )
        ai_text_cnv = generate_ai_text_nonsnv( assay, cnvwgs_iter, sample["groups"][0], "cnv" )
        #ai_text_bio = generate_ai_text_nonsnv( assay, biomarkers_iter_ai, sample["groups"][0], "bio" )
        ai_text_bio = ""
        ai_text = ai_text+ai_text_transloc+ai_text_cnv+ai_text_bio+conclusion
    else:
        ai_text = ai_text + conclusion
    disp_pos = []

    # this is stupid
    if "HD829" in sample["name"]:
        disp_pos = [133748283,31022441,31022903,39923086,119148988,25457243,148514471,28592642,28608046,28608047,48650385,128204841,209113113,90631838,5070021,5073770,25398281,170837543,115256529,36206711,198266713,106164914,7577559,
                    130872896,32434638,32435100,40063833,119278278,25234374,148817379,28018505,28033909,48791978,128485998,208248389,90088606,5070021,5073770,25245347,171410539,114713908,34834414,197401989,105243757,7674241]
    elif "HD827" in sample["name"]:
        disp_pos = [114713909,41224610,41224642,179218303,179234297,54733155,54736599,152323003,112840073,55174014,55174771,55181370,55181378,55191822,116699793,116795968,140753336,
                    136515302,43118395,25245347,25245350,28004077,32339421,7676154]
    trans = { 'nonsynonymous_SNV': 'missense SNV', 'stopgain': 'stop gain', 'frameshift_insertion': 'frameshift ins',
              'frameshift_deletion': 'frameshift del', 'nonframeshift_insertion': 'frameshift ins',  'nonframeshift_deletion': 'frameshift del',
              'missense_variant':'missense variant', 'feature_truncation':'feature truncation', 'frameshift_variant':'frameshift variant'}
    # this is to allow old samples to view plots, cnv + cnvprofile clash. Old assays used cnv as the entry for the plot, newer assays use cnv for path to cnv-file that was loaded.
    if "cnv" in sample:
        if sample["cnv"].lower().endswith(('.png', '.jpg', '.jpeg')):
            sample["cnvprofile"] = sample["cnv"]                                      

    sizefilter = sample_settings["max_cnv_size"]
    sizefilter_min = sample_settings["min_cnv_size"]
    return render_template('list_variants_vep.html', checked_genelists=genelist_filter, genelists_assay=genelists_assay, variants=variants, 
        sample=sample, form=form, translation=trans, hidden_comments=has_hidden_comments, dispgenes=filter_genes, 
        assay=assay, low_cov=low_cov, ai_text = ai_text, settings=settings, cnvwgs=cnvwgs_iter, cnvwgs_n=cnvwgs_iter_n, transloc=transloc_iter, 
        sizefilter=sizefilter, sizefilter_min=sizefilter_min, biomarker=biomarkers_iter, sample_ids=sample_ids, subpanel=subpanel, fusions=fusions, disp_pos=disp_pos
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