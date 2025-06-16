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

from flask import current_app as app
import os
from urllib.parse import unquote
from markupsafe import Markup, escape
import arrow
import dateutil


@app.template_filter()
def format_fusion_desc_few(st, preview_count=None):
    if not st:
        return ""

    good_terms = set(
        [
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
            "high",
        ]
    )
    verybad_terms = set(
        [
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
    )
    bad_terms = set(
        [
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
    )

    term_to_class = {
        **{term: "bg-green-500 text-white" for term in good_terms},
        **{term: "bg-red-500 text-white" for term in verybad_terms},
        **{term: "bg-pink-500 text-white" for term in bad_terms},
    }

    terms = st.split(",")

    if preview_count is not None:
        terms = terms[:preview_count]

    html_parts = []
    for i, v in enumerate(terms):
        v_clean = v.strip()
        term_class = term_to_class.get(v_clean, "bg-gray-500 text-white")
        html_parts.append(
            f"<span class='inline-block px-2 py-1 text-xs font-semibold {term_class} rounded-full mr-1 mb-1'>{escape(v_clean)}</span>"
        )
        if (i + 1) % 3 == 0 and (i + 1) != len(terms):
            html_parts.append("<br>")

    return Markup("".join(html_parts))


@app.template_filter()
def format_fusion_desc(st):
    if not st:
        return ""

    good_terms = set(
        [
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
            "high",
        ]
    )

    verybad_terms = set(
        [
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
    )

    bad_terms = set(
        [
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
    )

    # Define a dictionary mapping terms to Tailwind CSS classes
    term_to_class = {
        **{
            term: "bg-green-500 text-white" for term in good_terms
        },  # green background for good terms
        **{
            term: "bg-red-500 text-white" for term in verybad_terms
        },  # red background for very bad terms
        **{
            term: "bg-pink-500 text-white" for term in bad_terms
        },  # blue background for bad terms
    }

    # Truncate to first three words (for display purposes)
    terms = st.split(",")
    truncated_terms = terms[
        :100
    ]  # considering max 9 terms (3 rows of 3 terms)

    html_parts = []
    for i, v in enumerate(truncated_terms):
        term_class = term_to_class.get(v.strip(), "bg-gray-500 text-white")
        html_parts.append(
            f"<span class='inline-block px-2 py-1 text-xs font-semibold {term_class} rounded-full'>{escape(v.strip())}</span>"
        )
        if (i + 1) % 3 == 0 and (i + 1) != len(
            truncated_terms
        ):  # Insert a line break after every third term
            html_parts.append("<br>")

    return "".join(html_parts)


@app.template_filter()
def uniq_callers(calls):
    callers = []
    for c in calls:
        callers.append(c["caller"])
    return set(callers)


@app.template_filter()
def human_date(value):
    time_zone = "CET"
    return (
        arrow.get(value)
        .replace(tzinfo=dateutil.tz.gettz(time_zone))
        .humanize()
    )


@app.template_filter()
def format_comment(st):
    st = st.replace("\n", "<br />")
    return st
