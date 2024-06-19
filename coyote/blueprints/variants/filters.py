from flask import current_app as app
import os
import urllib
import re
from math import floor, log10
import dateutil
import arrow


@app.template_filter()
def format_panel_flag_snv(panel_str):
    if not panel_str:
        return ""
    genes = panel_str.split(",")

    classification = set()
    variant_type = set()
    for gene in genes:
        parts = panel_str.split(":")
        classification.add(parts[0])
        variant_type.add(parts[1])

    html = ""
    if "somatic" in classification:
        html = html + "<span class='filterwarn fusion-good'>*</span>"
    for vartype in variant_type:
        if vartype == "snv":
            html = html + "<span class='filterwarn fusion-good'>SNV</span>"
        else:
            html = html + "<span class='filterwarn fusion-bad'>" + vartype.upper() + "</span>"

    return html


@app.template_filter()
def format_filter(filters):

    html = ""
    pon_warn = False
    pon_fail = False
    pon_ffpe_warn = False
    pon_ffpe_fail = False
    for f in filters:
        if f == "PASS":
            html = html + "<span class='filterwarn fusion-good'>PASS</span>"
        if f == "GERMLINE":
            html = (
                html + "<span title='Germline variant' class='filterwarn fusion-good'>GERM</span>"
            )
        if f == "GERMLINE_RISK":
            html = html + "<span title='Germline risk' class='filterwarn fusion-bad'>GERM</span>"
        if f == "FAIL_NVAF":
            html = (
                html
                + "<span title='Too high VAF in normal sample' class='filterwarn fusion-verybad'>N</span>"
            )
        elif f == "FAIL_PVALUE":
            html = html + "<span title='Too low P-value' class='filterwarn fusion-verybad'>P</span>"
        elif "WARN_HOMOPOLYMER" in f:
            html = (
                html
                + "<span title='Variant in homopolymer' class='filterwarn fusion-bad'>HP</span>"
            )
        elif "WARN_STRANDBIAS" in f:
            html = html + "<span title='Strand bias' class='filterwarn fusion-bad'>SB</span>"
        elif "FAIL_STRANDBIAS" in f:
            html = html + "<span title='Strand bias' class='filterwarn fusion-verybad'>SB</span>"
        elif "FAIL_LONGDEL" in f:
            html = (
                html
                + "<span title='Long DEL from vardict' class='filterwarn fusion-verybad'>LD</span>"
            )
        elif f == "WARN_LOW_TVAF":
            html = html + "<span title='Low tumor VAF' class='filterwarn fusion-bad'>LO</span>"
        elif f == "WARN_VERYLOW_TVAF":
            html = (
                html + "<span title='Very low tumor VAF' class='filterwarn fusion-bad'>XLO</span>"
            )
        elif f == "WARN_NOVAR":
            pass
            # html = html + "<span class='filterwarn fusion-bad'>NO</span>"
        elif "WARN_PON" in f:
            if not pon_warn:
                pon_warn = True
                html = (
                    html
                    + "<span title='Variant seen in panel of normals' class='filterwarn fusion-bad'>PON</span>"
                )
        elif "FAIL_PON" in f:
            if not pon_fail:
                pon_fail = True
                html = (
                    html
                    + "<span title='Variant failed because seen in panel of normals' class='filterwarn fusion-verybad'>PON</span>"
                )
        elif "WARN_FFPE_PON" in f:
            if not pon_ffpe_warn:
                pon_ffpe_warn = True
                html = (
                    html
                    + "<span title='Variant seen in panel of FFPE-normals' class='filterwarn fusion-bad'>FFPE</span>"
                )
        elif "FAIL_FFPE_PON" in f:
            if not pon_ffpe_fail:
                pon_ffpe_fail = True
                html = (
                    html
                    + "<span title='Variant failed because seen in panel of FFPE-normals' class='filterwarn fusion-verybad'>FFPE</span>"
                )
        elif "FAIL" in f:
            html = html + "<span class='filterwarn fusion-verybad'>" + f + "</span>"
        elif "WARN" in f:
            html = html + "<span class='filterwarn fusion-bad'>" + f + "</span>"

    return html


@app.template_filter()
def intersect(l1, l2):
    overlap = list(set(l1) & set(l2))
    if len(overlap) > 0:
        return True
    else:
        return False


@app.template_filter()
def unesc(st):
    if st and len(st) > 0:
        return urllib.parse.unquote(st)
    else:
        return ""


@app.template_filter()
def format_fusion_desc(st):
    html = ""

    good_terms = [
        "mitelman",
        "18cancers",
        "known",
        "oncogene",
        "cgp",
        "cancer",
        "cosmic",
        "gliomas",
        "oesophagus",
        "tumor",
        "pancreases",
        "prostates",
        "tcga",
        "ticdb",
    ]

    verybad_terms = [
        "1000genomes",
        "banned",
        "bodymap2",
        "cacg",
        "conjoing",
        "cortex",
        "cta",
        "ctb",
        "ctc",
        "ctd",
        "distance1000bp",
        "ensembl_fully_overlapping",
        "ensembl_same_strand_overlapping",
        "gtex",
        "hpa",
        "matched-normal",
        "mt",
        "non_cancer_tissues",
        "non_tumor_cells",
        "pair_pseudo_genes",
        "paralogs",
        "readthrough",
        "refseq_fully_overlapping",
        "rp11",
        "rp",
        "rrna",
        "similar_reads",
        "similar_symbols",
        "ucsc_fully_overlapping",
        "ucsc_same_strand_overlapping",
    ]

    bad_terms = [
        "distance100kbp",
        "distance10kbp",
        "duplicates",
        "ensembl_partially_overlapping",
        "fragments",
        "healthy",
        "short_repeats",
        "long_repeats",
        "partial-matched-normal",
        "refseq_partially_overlapping",
        "short_distance" "ucsc_partially_overlapping",
    ]

    if st:
        vals = st.split(",")

        for v in vals:
            v_str = v
            v_str = v_str.replace("<", "&lt;")
            v_str = v_str.replace(">", "&gt;")
            if v in good_terms:
                html = html + "<span class='fusion fusion-good'>" + v_str + "</span>"
            elif v in verybad_terms:
                html = html + "<span class='fusion fusion-verybad'>" + v_str + "</span>"
            elif v in bad_terms:
                html = html + "<span class='fusion fusion-bad'>" + v_str + "</span>"
            else:
                html = html + "<span class='fusion fusion-neutral'>" + v_str + "</span>"

    return html


@app.template_filter()
def uniq_callers(calls):
    callers = []
    for c in calls:
        callers.append(c["caller"])
    return set(callers)


@app.template_filter()
def format_comment(st):
    st = st.replace("\n", "<br />")
    return st


@app.template_filter()
def basename(path):
    return os.path.basename(path)


@app.template_filter()
def no_transid(nom):
    a = nom.split(":")
    if 1 < len(a):
        return a[1]


@app.template_filter()
def format_hotspot(filters):
    """
    Gives hotspot icons a special color depending on what type of hotspot. This function really is only useful for
    solid cancers and very specific to the SomaticPanelPipeine vep annotation.
    """
    html = ""
    for f in filters:

        if "mm" in f:
            html = (
                html
                + "<span title='Present in Melanoma hotspot list' span class='filterwarn fusion-bad'>MM</span>"
            )
        if "cns" in f:
            html = (
                html
                + "<span title='Present in CNS hotspot list' span class='filterwarn fusion-good'>CNS</span>"
            )
        if "lu" in f:
            html = (
                html
                + "<span title='Present in Lung hotspot list' span class='filterwarn fusion-verybad'>LU</span>"
            )
        if "co" in f:
            html = (
                html
                + "<span title='Present in Colon hotspot list' span class='filterwarn fusion-neutral'>CO</span>"
            )
        if "gi" in f:
            html = (
                html
                + "<span title='Present in Gastro Intenstinal hotspot list' span class='filterwarn fusion-bad'>GI</span>"
            )
        if "d" in f:
            html = (
                html
                + "<span title='Present in DNA-panel hotspot list' span class='filterwarn fusion-bad'>D</span>"
            )

    return html


@app.template_filter()
def one_letter_p(st: str) -> str | None:
    """
    Convert three-letter amino acid code to one-letter code.
    """
    aa = {
        "Cys": "C",
        "Asp": "D",
        "Ser": "S",
        "Gln": "Q",
        "Lys": "K",
        "Ile": "I",
        "Pro": "P",
        "Thr": "T",
        "Phe": "F",
        "Asn": "N",
        "Gly": "G",
        "His": "H",
        "Leu": "L",
        "Arg": "R",
        "Trp": "W",
        "Ala": "A",
        "Val": "V",
        "Glu": "E",
        "Tyr": "Y",
        "Met": "M",
        "Ter": "*",
    }

    pattern = re.compile("|".join(aa.keys()))
    if st:
        return pattern.sub(lambda x: aa[x.group()], st)

    return ""


@app.template_filter()
def ellipsify(st, l):
    if len(st) <= l:
        return st
    else:
        return "<span title='" + st + "'>" + st[0:l] + "...</span>"


@app.template_filter()
def multirow(st):
    if isinstance(st, list):
        return "<br>".join(st)
    else:
        return "<br>".join(st.split("&"))


@app.template_filter()
def round_to_3(x):
    if x == 0:
        return 0
    return round(x, -int(floor(log10(abs(x)))) + 2)


@app.template_filter()
def format_gnomad(st):
    if not st:
        return ""
    return str(round_to_3(float(st * 100))) + "%"


@app.template_filter()
def format_pop_freq(st, allele_to_show):
    if not st:
        return ""
    if len(allele_to_show) > 1:
        allele_to_show = allele_to_show[1:]
    all_alleles = st.split("&")
    for allele_frq in all_alleles:
        a = allele_frq.split(":")
        if a[0] == allele_to_show:
            return str(round_to_3(float(a[1]) * 100)) + "%"

    return "N/A"


@app.template_filter()
def human_date(value):
    time_zone = "CET"
    return arrow.get(value).replace(tzinfo=dateutil.tz.gettz(time_zone)).humanize()


@app.template_filter()
def array_uniq(arr):
    uniq = set()
    for a in arr:
        uniq.add(a)
    return uniq


@app.template_filter()
def format_oncokbtext(st):
    st = st.replace("\n", "<br />")
    l = re.findall("\(PMID:.*?\)", st)
    i = 0
    for a in l:
        b = a.replace(")", "")
        b = b.replace("(PMID:", "")
        b = b.replace(" ", "")

        pmids = b.split(",")

        linked_str = ""
        for pmid in pmids:
            i = i + 1
            linked_str = (
                linked_str
                + "<a href='https://www.ncbi.nlm.nih.gov/pubmed/"
                + pmid
                + "'>"
                + str(i)
                + "</a> "
            )

        linked_str = linked_str.rstrip()
        st = st.replace(a, "<b>[" + linked_str + "]</b>")

    return st
