from flask import current_app as app
import os
import urllib
import re
from math import floor, log10
import dateutil
import arrow
from markupsafe import Markup


@app.template_filter("has_hotspot")
def has_hotspot_filter(variants):
    return any(variant.get("hotspot") for variant in variants)


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
        html = (
            html
            + "<span class='inline-block px-1 mx-1 rounded-full text-xs bg-green-100 '>*</span>"
        )
    for vartype in variant_type:
        if vartype == "snv":
            html = (
                html
                + "<span class='inline-block px-1 py-1 mx-1 my-1 my-1 rounded-full text-xs bg-green-100'>SNV</span>"
            )
        else:
            html = (
                html
                + "<span class='inline-block px-1 py-1 mx-1 my-1 my-1 rounded-full text-xs bg-red-100'>"
                + vartype.upper()
                + "</span>"
            )

    return html


@app.template_filter()
def sortable_date(value):
    s = str(value).translate("- :.")
    return s


@app.template_filter()
def standard_HGVS(st):
    if st:
        parts = st.rsplit(".", 1)
        standard = parts[0] + ".(" + parts[1] + ")"
    else:
        standard = ""
    return Markup.escape(standard)


@app.template_filter()
def perc_no_dec(val):
    if val and (val != "" or val != "NA"):
        return f"{str(int(round(100 * val, 0)))}%"


@app.template_filter()
def format_tier(st):
    if st == 1:
        return "Tier I"
    if st == 2:
        return "Tier II"
    if st == 3:
        return "Tier III"
    if st == 4:
        return "Tier IV"
    return st


@app.template_filter()
def format_filter(filters):
    """Formats variant filters into colored badges with tooltips and wrapping behavior"""

    # Define color categories and tooltips
    filter_classes = {
        "PASS": ("PASS", "bg-pass", "Variant passed all quality filters"),
        "GERMLINE": ("GERM", "bg-germline", "Germline variant"),
        "GERMLINE_RISK": ("GERM", "bg-germline-risk", "Germline risk variant"),
    }

    warn_filters = {
        "HP": ("HP", "bg-warn", "Variant in homopolymer"),
        "SB": ("SB", "bg-warn", "Strand bias detected"),
        "LO": ("LO", "bg-warn", "Low tumor VAF"),
        "XLO": ("XLO", "bg-warn", "Very low tumor VAF"),
        "PON": ("PON", "bg-warn", "Variant in panel of normals"),
        "FFPE": ("FFPE", "bg-warn", "Variant in panel of FFPE-normals"),
    }

    fail_filters = {
        "N": ("N", "bg-fail", "Too high VAF in normal sample"),
        "P": ("P", "bg-fail", "Too low P-value"),
        "SB": ("SB", "bg-fail", "Strand bias failed"),
        "LD": ("LD", "bg-fail", "Long deletion detected"),
        "PON": ("PON", "bg-fail", "Variant failed due to panel of normals"),
        "FFPE": ("FFPE", "bg-fail", "Variant failed due to FFPE panel"),
    }

    # Mapping of multiple raw filter names to grouped categories
    warn_map = {
        "WARN_HOMOPOLYMER": "HP",
        "WARN_STRANDBIAS": "SB",
        "WARN_LOW_TVAF": "LO",
        "WARN_VERYLOW_TVAF": "XLO",
        "WARN_PON_freebayes": "PON",
        "WARN_PON_vardict": "PON",
        "WARN_PON_tnscope": "PON",
        "WARN_FFPE_PON_freebayes": "FFPE",
        "WARN_FFPE_PON_vardict": "FFPE",
        "WARN_FFPE_PON_tnscope": "FFPE",
    }

    fail_map = {
        "FAIL_NVAF": "N",
        "FAIL_PVALUE": "P",
        "FAIL_STRANDBIAS": "SB",
        "FAIL_LONGDEL": "LD",
        "FAIL_PON_freebayes": "PON",
        "FAIL_PON_vardict": "PON",
        "FAIL_PON_tnscope": "PON",
        "FAIL_FFPE_PON_freebayes": "FFPE",
        "FAIL_FFPE_PON_vardict": "FFPE",
        "FAIL_FFPE_PON_tnscope": "FFPE",
    }

    skip_filters = ["WARN_NOVAR"]

    html = ""
    seen_flags = set()

    for f in filters:
        if f in filter_classes:
            text, css_class, tooltip = filter_classes[f]
            seen_flags.add(f)
        elif f in warn_map:
            if warn_map[f] in seen_flags:
                continue
            else:
                text, css_class, tooltip = warn_filters[warn_map[f]]
                seen_flags.add(text)
        elif f in fail_map:
            if fail_map[f] in seen_flags:
                continue
            else:
                text, css_class, tooltip = fail_filters[fail_map[f]]
                seen_flags.add(text)
        elif f in skip_filters:
            seen_flags.add(f)
            continue
        elif "FAIL" in f and f not in seen_flags:
            text, css_class, tooltip = f, "bg-fail", "Failure due to quality issues"
            seen_flags.add(f)
        elif "WARN" in f and f not in seen_flags:
            text, css_class, tooltip = f, "bg-warn", "Warning due to quality concerns"
            seen_flags.add(f)
        else:
            continue  # Ignore unknown filters

        html += (
            f"<div class='inline-block p-1 text-white {css_class} rounded-md text-xs leading-tight flex items-center' "
            f"onmouseover='showTooltip(event, \"{tooltip}\")'>"
            f"{text}</div>"
        )

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


@app.template_filter(name="format_hotspot_note")
def format_hotspot_note(dummy):
    html = ""
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-melanoma rounded-full'>MM: Malignt Melanom</span>&nbsp;"
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-cns rounded-full'>CNS: Centrala Nervsystemet</span>&nbsp;"
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-lung rounded-full'>LU: Lunga</span>&nbsp;"
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-colon rounded-full'>CO: Kolorektal</span>&nbsp;"
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-gi rounded-full'>GI: Gastro-Intestinal</span>&nbsp;"
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-dna rounded-full'>D: Generell Solid</span>&nbsp;"
    return html


@app.template_filter()
def format_hotspot(filters):
    """
    Gives hotspot icons a special color depending on what type of hotspot. This function really is only useful for
    solid cancers and very specific to the SomaticPanelPipeline VEP annotation.
    """
    html = ""
    for f in filters:
        if "mm" in f:
            html += "<span title='Present in Melanoma hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-melanoma rounded-full'>MM</span>"
        if "cns" in f:
            html += "<span title='Present in CNS hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-cns rounded-full'>CNS</span>"
        if "lu" in f:
            html += "<span title='Present in Lung hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-lung rounded-full'>LU</span>"
        if "co" in f:
            html += "<span title='Present in Colon hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-colon rounded-full'>CO</span>"
        if "gi" in f:
            html += "<span title='Present in Gastro Intestinal hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-gi rounded-full'>GI</span>"
        if "d" in f:
            html += "<span title='Present in DNA-panel hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-dna rounded-full'>D</span>"

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
        return "-"
    return str(round_to_3(float(st * 100))) + "%"


@app.template_filter()
def format_pop_freq(st, allele_to_show):
    if not st:
        return "-"
    if len(allele_to_show) > 1:
        allele_to_show = allele_to_show[1:]
    all_alleles = st.split("&")
    for allele_frq in all_alleles:
        a = allele_frq.split(":")
        if a[0] == allele_to_show:
            return str(round_to_3(float(a[1]) * 100)) + "%"

    return "N/A"


def remove_prefix(text, prefix):
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


@app.template_filter()
def pubmed_links(st):

    if not st:
        return "-"
    pids = re.split(r",\s*", st)
    outstr = "<b>["
    for i, pid in enumerate(pids):
        pid = remove_prefix(pid, "PMID:")
        outstr = (
            outstr
            + "<a href='https://www.ncbi.nlm.nih.gov/pubmed/"
            + pid
            + "'>"
            + str(i + 1)
            + "</a> "
        )

    outstr = outstr.rstrip()
    outstr = outstr + "]</b>"

    return outstr


@app.template_filter()
def three_dec(val):
    return str(round_to_3(float(val) * 100))


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
    l = re.findall(r"\(PMID:.*?\)", st)
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


@app.template_filter()
def regex_replace(s, find, replace):
    return re.sub(find, replace, s)
