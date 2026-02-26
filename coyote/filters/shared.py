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

"""Shared, pure helpers used by Jinja filter wrappers."""

from datetime import datetime, tzinfo

import arrow
import markdown
from dateutil import tz
from markupsafe import Markup, escape


STOCKHOLM: tzinfo | None = tz.gettz("Europe/Stockholm")

GOOD_FUSION_TERMS = {
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
}

VERY_BAD_FUSION_TERMS = {
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
}

BAD_FUSION_TERMS = {
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
}

FUSION_TERM_CLASS = {
    **{term: "bg-green-500 text-white" for term in GOOD_FUSION_TERMS},
    **{term: "bg-red-500 text-white" for term in VERY_BAD_FUSION_TERMS},
    **{term: "bg-pink-500 text-white" for term in BAD_FUSION_TERMS},
}

LEGACY_GOOD_FUSION_TERMS = {
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
}

LEGACY_VERY_BAD_FUSION_TERMS = {
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
}

LEGACY_BAD_FUSION_TERMS = {
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
}


def human_date(value: datetime | str) -> str:
    """Return a humanized relative date in Stockholm timezone."""
    if not value:
        return "N/A"

    try:
        dt = arrow.get(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=STOCKHOLM)
        dt = dt.to(STOCKHOLM)
        now = arrow.now(STOCKHOLM)
        return dt.humanize(now)
    except Exception:
        return "Invalid date"


def format_comment_markdown(st: str | None) -> str:
    """Render markdown safely for UI comment blocks."""
    if not st:
        return ""

    st = st.replace("\r\n", "\n").replace("\r", "\n")
    st = escape(st)
    html = markdown.markdown(
        st,
        extensions=[
            "extra",
            "sane_lists",
            "nl2br",
            "toc",
            "tables",
            "fenced_code",
        ],
    )
    return Markup(html)


def format_fusion_desc_badges(st: str | None, preview_count: int | None = None) -> str:
    """Render fusion description tokens as color-coded badge HTML."""
    if not st:
        return ""

    terms = st.split(",")
    if preview_count is not None:
        terms = terms[:preview_count]

    html_parts = []
    for i, term in enumerate(terms):
        term_clean = term.strip()
        term_class = FUSION_TERM_CLASS.get(term_clean, "bg-gray-500 text-white")
        html_parts.append(
            f"<span class='inline-block px-2 py-1 text-xs font-semibold {term_class} rounded-full mr-1 mb-1'>{escape(term_clean)}</span>"
        )
        if (i + 1) % 3 == 0 and (i + 1) != len(terms):
            html_parts.append("<br>")

    return Markup("".join(html_parts))


def format_fusion_desc_legacy(st: str | None) -> str:
    """Render legacy fusion spans (`fusion-*` classes) used by DNA templates."""
    if not st:
        return ""

    html_parts = []
    for value in st.split(","):
        token = value.replace("<", "&lt;").replace(">", "&gt;")
        if value in LEGACY_GOOD_FUSION_TERMS:
            klass = "fusion fusion-good"
        elif value in LEGACY_VERY_BAD_FUSION_TERMS:
            klass = "fusion fusion-verybad"
        elif value in LEGACY_BAD_FUSION_TERMS:
            klass = "fusion fusion-bad"
        else:
            klass = "fusion fusion-neutral"
        html_parts.append(f"<span class='{klass}'>{token}</span>")
    return "".join(html_parts)


def uniq_callers(calls: list) -> set:
    """Return unique caller names from a list of call dicts."""
    return {c.get("caller") for c in calls if isinstance(c, dict) and c.get("caller")}


def shorten_number(n: int | float) -> str:
    """Format large numbers using metric suffixes."""
    for unit in ["", "K", "M", "B", "T"]:
        if abs(n) < 1000:
            if float(n).is_integer():
                return f"{int(n)}{unit}"
            return f"{n:.1f}{unit}".rstrip("0").rstrip(".")
        n /= 1000
    if float(n).is_integer():
        return f"{int(n)}P"
    return f"{n:.1f}P".rstrip("0").rstrip(".")


def render_markdown_basic(text: str | None) -> str:
    """Render markdown with default parser settings."""
    if not text:
        return ""
    return Markup(markdown.markdown(text))


def render_markdown_rich(text: str | None) -> str:
    """Render markdown with richer extensions used in home templates."""
    if not text:
        return ""
    html = markdown.markdown(text, extensions=["extra", "tables", "sane_lists"])
    return Markup(html)
