# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Presentation-only analysis priorities, independent of finding eligibility."""

from collections.abc import Iterable, Sequence


def analysis_priority(analyses: Iterable[str], order: Sequence[str]) -> int:
    """Rank a summary group by its first configured analysis, preserving unlisted groups.

    Args:
        analyses: Analyses represented by a section or combined table.
        order: Optional analysis priority; an empty sequence leaves all ranks equal.

    Returns:
        Lowest configured position, or the position after all explicitly listed analyses.
    """
    positions = {analysis: index for index, analysis in enumerate(order)}
    return min((positions.get(analysis, len(order)) for analysis in analyses), default=len(order))


def order_summary_tables(
    sections: list[dict], order: list[str], biomarker_analyses: Iterable[str] = ()
) -> None:
    """Reorder only summary tables in place, leaving other document content untouched.

    Args:
        sections: Native package document sections, before the conclusion and detail cards.
        order: Configured analysis priority; an empty list preserves current table order.
        biomarker_analyses: Actual analyses represented in the combined biomarker table.
    """
    analyses = {
        "snvs": {"SNV"},
        "germline_snvs": {"SNV"},
        "cnvs": {"CNV"},
        "translocations": {"TRANSLOCATION"},
        "fusions": {"FUSION"},
        "biomarkers": set(biomarker_analyses),
        "pgx": {"PGX"},
        **{
            f"empty-{analysis.lower()}": {analysis}
            for analysis in ("HRD", "MSI", "TMB", "BIOMARKER")
        },
    }
    indexes = [index for index, section in enumerate(sections) if section["key"] in analyses]
    ordered = sorted(
        (sections[index] for index in indexes),
        key=lambda section: analysis_priority(analyses[section["key"]], order),
    )
    for index, section in zip(indexes, ordered):
        sections[index] = section
