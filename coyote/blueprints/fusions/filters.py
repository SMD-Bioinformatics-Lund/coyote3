from flask import current_app as app
import os
from urllib.parse import unquote



@app.template_filter()
def format_fusion_desc(st):
    html = ""

    good_terms = [
        "mitelman","18cancers", "known", "oncogene", "cgp", "cancer", "cosmic", "gliomas", "oesophagus","tumor",
        "pancreases", "prostates", "tcga", "ticdb"
    ]        
    verybad_terms = [
        "1000genomes", "banned", "bodymap2", "cacg", "conjoing", "cortex", "cta", "ctb",
        "ctc", "ctd", "distance1000bp", "ensembl_fully_overlapping", "ensembl_same_strand_overlapping",
        "gtex", "hpa", "matched-normal", "mt", "non_cancer_tissues", "non_tumor_cells", "pair_pseudo_genes",
        "paralogs", "readthrough", "refseq_fully_overlapping", "rp11", "rp", "rrna", "similar_reads",
        "similar_symbols", "ucsc_fully_overlapping", "ucsc_same_strand_overlapping"
    ]       
    bad_terms = [
        "distance100kbp","distance10kbp","duplicates", "ensembl_partially_overlapping","fragments", "healthy",
        "short_repeats", "long_repeats", "partial-matched-normal", "refseq_partially_overlapping", "short_distance"
        "ucsc_partially_overlapping"
    ]
    
    if st:
        vals = st.split(',')

        for v in vals:
            v_str = v
            v_str = v_str.replace("<", "&lt;")
            v_str = v_str.replace(">", "&gt;")
            if v in good_terms:
                html = html + "<span class='fusion fusion-good'>"+v_str+"</span>"
            elif v in verybad_terms:
                html = html + "<span class='fusion fusion-verybad'>"+v_str+"</span>"
            elif v in bad_terms:
                html = html + "<span class='fusion fusion-bad'>"+v_str+"</span>"
            else:
                html = html + "<span class='fusion fusion-neutral'>"+v_str+"</span>"
                
    return html


@app.template_filter()
def uniq_callers(calls):
    callers = []
    for c in calls:
        callers.append(c["caller"])
    return set(callers)




