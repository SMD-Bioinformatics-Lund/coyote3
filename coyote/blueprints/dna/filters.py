#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

"""
This module provides a collection of Jinja2 template filters for use in Flask-based
genomic data analysis and reporting applications. The filters support formatting,
annotation, and transformation of variant and clinical data for display in web templates.

Key functionalities include:
- Formatting variant filters, flags, and annotations as HTML badges or tooltips.
- Converting and formatting dates, percentages, and frequencies.
- Handling gene panel strings, fusion descriptions, and amino acid codes.
- Generating PubMed links and processing comments for display.
- Utility filters for string manipulation, set operations, and rounding.
"""

from flask import current_app as app
import os
import re
from math import floor, log10
import arrow
from markupsafe import Markup, escape
import markdown
from datetime import datetime
from dateutil import tz
from urllib.parse import unquote


@app.template_filter("has_hotspot")
def has_hotspot_filter(variants: list) -> bool:
    """
    Returns True if any variant in the list has the 'hotspot' key set to a truthy value.

    Args:
        variants (list): List of variant dictionaries.

    Returns:
        bool: True if any variant has 'hotspot' set, otherwise False.
    """
    return any(variant.get("hotspot") for variant in variants)


@app.template_filter()
def format_panel_flag_snv(panel_str: str) -> str:
    """
    Formats a gene panel string for SNV (single nucleotide variant) flags as HTML badges.

    Args:
        panel_str (str): A string containing gene panel information, typically in the format
        'classification:variant_type' separated by commas for multiple entries.

    Returns:
        str: HTML string with formatted badges for each classification and variant type.
    """
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
def sortable_date(value: datetime | str) -> str:
    """
    Converts a date or datetime value to a sortable string by removing dashes, spaces, colons, and periods.

    Args:
        value: The date or datetime value to be formatted.

    Returns:
        str: A string representation of the date with special characters removed, suitable for sorting.
    """
    s = str(value).translate("- :.")
    return s


@app.template_filter()
def standard_HGVS(st: str | None) -> str:
    """
    Formats a standard HGVS string by removing the version number after the last dot and wrapping it in parentheses.

    Args:
        st (str | None): The HGVS string to format, e.g., 'NM_000546.5'.

    Returns:
        str: The formatted HGVS string with the version in parentheses, e.g., 'NM_000546.(5)'. Returns an empty string if input is None or empty.
    """
    if st:
        parts = st.rsplit(".", 1)
        standard = parts[0] + ".(" + parts[1] + ")"
    else:
        standard = ""
    return Markup.escape(standard)


@app.template_filter()
def perc_no_dec(val: float | None) -> str | None:
    """
    Converts a float value to a percentage string with no decimal places.

    Args:
        val (float | None): The value to convert (e.g., 0.25 for 25%).

    Returns:
        str | None: The formatted percentage string (e.g., '25%'), or None if input is invalid.
    """
    if isinstance(val, (int, float)) and val not in ("", "NA", None):
        return f"{int(round(100 * val, 0))}%"
    return None


@app.template_filter()
def format_tier(st: int | str) -> str:
    """
    Formats a tier value as a human-readable string.

    Args:
        st (int | str): The tier value (1, 2, 3, 4 or string).

    Returns:
        str: The formatted tier string (e.g., 'Tier I'), or the original value if not 1-4.
    """
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
def format_filter(filters: list) -> str:
    """
    Formats a list of variant filters as HTML badges with appropriate colors and tooltips.

    Args:
        filters (list): List of filter strings applied to a variant.

    Returns:
        str: HTML string with formatted badges for each filter, including tooltips and color coding.
    """

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
            text, css_class, tooltip = (
                f,
                "bg-fail",
                "Failure due to quality issues",
            )
            seen_flags.add(f)
        elif "WARN" in f and f not in seen_flags:
            text, css_class, tooltip = (
                f,
                "bg-warn",
                "Warning due to quality concerns",
            )
            seen_flags.add(f)
        else:
            continue  # Ignore unknown filters

        html += (
            f"<div data-export-value='{text}' class='inline-block p-1 text-white {css_class} rounded-md text-xs leading-tight flex items-center' "
            f"onmouseover='showTooltip(event, \"{tooltip}\")'>"
            f"{text}</div>"
        )

    return html


@app.template_filter()
def intersect(l1: list, l2: list) -> bool:
    """
    Checks if there is any overlap between two lists.

    Args:
        l1 (list): First list.
        l2 (list): Second list.

    Returns:
        bool: True if there is at least one common element, False otherwise.
    """
    overlap = list(set(l1) & set(l2))
    if len(overlap) > 0:
        return True
    else:
        return False


@app.template_filter()
def unesc(st: str | None) -> str:
    """
    Decodes a percent-encoded string using URL decoding.

    Args:
        st (str | None): The percent-encoded string to decode.

    Returns:
        str: The decoded string, or an empty string if the input is None or empty.
    """
    if st and len(st) > 0:
        return unquote(st)
    else:
        return ""


@app.template_filter()
def format_fusion_desc(st: str | None) -> str:
    """
    Formats a fusion description string by categorizing each term as good, bad, very bad, or neutral, and wraps them in corresponding HTML span elements for display.

    Args:
        st (str | None): A comma-separated string of fusion description terms.

    Returns:
        str: HTML string with each term wrapped in a span with a class indicating its category.
    """
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
        "short_distance",
        "ucsc_partially_overlapping",
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
def uniq_callers(calls: list) -> set:
    """
    Extracts unique caller names from a list of call dictionaries.

    Args:
        calls (list): List of dictionaries, each containing a "caller" key.

    Returns:
        set: Set of unique caller names.
    """
    callers = []
    for c in calls:
        callers.append(c["caller"])
    return set(callers)


@app.template_filter()
def format_comment(st: str | None) -> str:
    """
    Render full GitHub-style markdown safely:
    - Supports headings (##)
    - Lists
    - Paragraphs
    - Bold/italics
    - Line breaks
    - Code blocks
    - Tables
    - Links
    - CRLF normalization
    """
    if not st:
        return ""

    # Normalize all newline types → "\n"
    st = st.replace("\r\n", "\n").replace("\r", "\n")

    # Escape unsafe HTML BEFORE markdown processing
    st = escape(st)

    # Render using GitHub-style markdown extensions
    html = markdown.markdown(
        st,
        extensions=[
            "extra",  # tables, code, lists, etc.
            "sane_lists",
            "nl2br",  # convert single newlines → <br>
            "toc",  # heading anchors
            "tables",  # GitHub table syntax
            "fenced_code",  # ``` code blocks
        ],
    )

    return Markup(html)


@app.template_filter("markdown")
def markdown_filter(s):
    return markdown.markdown(s)


@app.template_filter()
def basename(path: str) -> str:
    """
    Extracts and returns the base name (the final component) from a given file path.

    Args:
        path (str): The file path from which to extract the base name.

    Returns:
        str: The base name of the file path.
    """
    return os.path.basename(path)


@app.template_filter()
def no_transid(nom: str) -> str | None:
    """
    Extracts the transcript ID from a colon-separated string.

    Args:
        nom (str): A string in the format 'gene:transcript_id'.

    Returns:
        str | None: The transcript ID if present, otherwise None.
    """
    a = nom.split(":")
    if 1 < len(a):
        return a[1]

    return None


@app.template_filter(name="format_hotspot_note")
def format_hotspot_note(dummy) -> str:
    """
    Generates a legend of hotspot types as colored HTML badges for display in templates.

    Args:
        dummy: Placeholder argument (not used).

    Returns:
        str: HTML string with colored badges and their corresponding cancer type descriptions.
    """
    html = ""
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-melanoma rounded-full'>MM: Malignt Melanom</span>&nbsp;"
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-cns rounded-full'>CNS: Centrala Nervsystemet</span>&nbsp;"
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-lung rounded-full'>LU: Lunga</span>&nbsp;"
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-colon rounded-full'>CO: Kolorektal</span>&nbsp;"
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-gi rounded-full'>GI: Gastro-Intestinal</span>&nbsp;"
    html += "<span class='inline-block p-1 m-1 text-xs text-white bg-dna rounded-full'>D: Generell Solid</span>&nbsp;"
    return html


@app.template_filter()
def format_hotspot(filters: list) -> str:
    """
    Gives hotspot icons a special color depending on what type of hotspot. This function really is only useful for
    solid cancers and very specific to the SomaticPanelPipeline VEP annotation.
    """
    html = ""
    for f in filters:
        if "mm" in f:
            html += "<span data-export-value='mm' title='Present in Melanoma hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-melanoma rounded-full'>MM</span>"
        if "cns" in f:
            html += "<span data-export-value='cns' title='Present in CNS hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-cns rounded-full'>CNS</span>"
        if "lu" in f:
            html += "<span data-export-value='lu' title='Present in Lung hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-lung rounded-full'>LU</span>"
        if "co" in f:
            html += "<span data-export-value='co' title='Present in Colon hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-colon rounded-full'>CO</span>"
        if "gi" in f:
            html += "<span data-export-value='gi' title='Present in Gastro Intestinal hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-gi rounded-full'>GI</span>"
        if "d" in f:
            html += "<span data-export-value='d' title='Present in DNA-panel hotspot list' class='inline-block px-1 py-1 mx-1 my-1 text-xs font-semibold text-white bg-dna rounded-full'>D</span>"

    return html


@app.template_filter()
def one_letter_p(st: str) -> str | None:
    """
    Converts a three-letter amino acid code to its corresponding one-letter code.

    Returns the input string with all three-letter amino acid codes replaced by their one-letter equivalents.
    If the input is None or empty, returns an empty string.

    Args:
        st (str): The string containing three-letter amino acid codes.

    Returns:
        str | None: The string with three-letter codes replaced by one-letter codes, or an empty string if input is None.
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
def ellipsify(st: str, l: int) -> str:
    """
    Truncates a string to a specified length and adds an ellipsis with a tooltip showing the full string.

    Args:
        st (str): The input string to truncate.
        l (int): The maximum length of the truncated string.

    Returns:
        str: The truncated string with an ellipsis and a tooltip containing the full string if it exceeds the specified length.
    """
    if len(st) <= l:
        return st
    else:
        return "<span title='" + st + "'>" + st[0:l] + "...</span>"


@app.template_filter()
def multirow(st: str | list) -> str:
    """
    Joins a list or a string (split by '&') into a multi-row HTML string separated by <br> tags.

    Args:
        st (str | list): The input, either a list of strings or a single string with '&' as separator.

    Returns:
        str: The joined string with <br> tags for multi-row display.
    """
    if isinstance(st, list):
        return "<br>".join(st)
    else:
        return "<br>".join(st.split("&"))


@app.template_filter()
def round_to_3(x: float | int) -> float:
    """
    Rounds a number to 3 significant digits.

    Args:
        x (float | int): The number to round.

    Returns:
        float: The number rounded to 3 significant digits, or 0 if x is 0.
    """
    if x == 0:
        return 0
    return round(x, -int(floor(log10(abs(x)))) + 2)


@app.template_filter()
def format_gnomad(st: str | None) -> str:
    """
    Formats a gnomAD frequency value as a percentage string with up to 3 significant digits.

    Args:
        st (str | None): The gnomAD frequency value as a string (e.g., '0.000123').

    Returns:
        str: The formatted frequency as a percentage string (e.g., '0.0123%'), or '-' if input is None or empty.
    """
    if not st:
        return "-"
    if isinstance(st, str):
        st = st.strip()
    return str(round_to_3(float(st) * 100)) + "%"


@app.template_filter()
def format_pop_freq(st: str, allele_to_show: str) -> str:
    """
    Formats a population frequency string for a specific allele as a percentage with up to 3 significant digits.

    Args:
        st (str): Population frequency string, with allele:frequency pairs separated by '&', e.g., 'A:0.001&C:0.002'.
        allele_to_show (str): The allele for which to display the frequency.

    Returns:
        str: The formatted frequency as a percentage string (e.g., '0.1%'), '-' if input is empty, or 'N/A' if the allele is not found.
    """
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


def remove_prefix(text: str, prefix: str) -> str:
    """
    Removes the specified prefix from the given text if it starts with that prefix.

    Args:
        text (str): The input string to process.
        prefix (str): The prefix to remove from the input string.

    Returns:
        str: The string with the prefix removed if present, otherwise the original string.
    """
    if text.startswith(prefix):
        return text[len(prefix) :]
    return text


@app.template_filter()
def pubmed_links(st: str | None) -> str:
    """
    Converts a comma-separated string of PubMed IDs (optionally prefixed with 'PMID:') into a series of numbered HTML links.

    Args:
        st (str | None): A string containing PubMed IDs separated by commas, e.g., 'PMID:12345,PMID:67890' or '12345,67890'.

    Returns:
        str: An HTML string with each PubMed ID converted to a numbered link, or '-' if input is None or empty.
    """
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
    outstr += "]</b>"

    return outstr


@app.template_filter()
def three_dec(val: float | int) -> str:
    """
    Converts a numeric value to a percentage string with up to 3 significant digits.

    Args:
        val: The numeric value to convert (e.g., 0.01234 for 1.234%).

    Returns:
        str: The value multiplied by 100, rounded to 3 significant digits, as a string.
    """
    return str(round_to_3(float(val) * 100))


@app.template_filter()
def human_date(value: datetime | str) -> str:
    """
    Converts a date or datetime value to a human-readable relative time string
    (e.g., '3 days ago') in Central European Time (CET).

    Args:
        value (datetime | str): The input date or datetime string.

    Returns:
        str: A human-readable relative time string in CET timezone.
    """
    if not value:
        return "N/A"

    try:
        # Parse string to datetime if needed
        dt = arrow.get(value)
    except (arrow.parser.ParserError, ValueError, TypeError):
        return "Invalid date"

    cet = tz.gettz("Europe/Stockholm")
    return dt.to(cet).humanize()


@app.template_filter()
def array_uniq(arr: list) -> set:
    """
    Returns a set of unique elements from the input list.

    Args:
        arr (list): The list from which to extract unique elements.

    Returns:
        set: A set containing the unique elements from the input list.
    """
    uniq = set()
    for a in arr:
        uniq.add(a)
    return uniq


@app.template_filter()
def format_oncokbtext(st: str) -> str:
    """
    Formats ONCOKB text for HTML display by replacing newlines with <br /> tags and converting
    any (PMID:...) references into numbered PubMed links.

    Args:
        st (str): The ONCOKB text string to format.

    Returns:
        str: The formatted string with newlines replaced by <br /> and PubMed references as links.
    """
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
            i += 1
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
def regex_replace(s: str, find: str, replace: str) -> str:
    """
    Replaces all occurrences of a regex pattern in a string with a replacement string.

    Args:
        s (str): The input string to process.
        find (str): The regex pattern to search for.
        replace (str): The replacement string.

    Returns:
        str: The string with all matches of the pattern replaced.
    """
    return re.sub(find, replace, s)
