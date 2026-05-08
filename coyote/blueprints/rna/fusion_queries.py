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

import re
from typing import Any, Dict


def _coerce_nonnegative_int(value: Any, default: int = 0) -> int:
    """
    Coerce incoming filter values to non-negative ints.
    Handles form/post values that may arrive as strings.
    """
    try:
        parsed = int(value)
        return parsed if parsed >= 0 else default
    except (TypeError, ValueError):
        return default


def fusion_annotation_filters(settings: Dict[str, Any]) -> list:
    """
    Return desc annotation terms selected via the Annotation Filters UI.

    These terms are stored in ``sample.filters.fusion_description`` and used
    as positive-inclusion patterns: a fusion is kept when at least one of its
    calls has a ``desc`` field that matches any of the returned terms.

    Args:
        settings: Query-settings dict.  Reads ``fusion_description`` (list[str]).

    Returns:
        List of raw term strings (e.g. ``["known", "oncogene"]``).
    """
    return list(settings.get("fusion_description") or [])


def build_fusion_query(assay_group: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a MongoDB query to retrieve fusion data for a given sample.

    Two independent filters are applied:

    * **Desc filter** – annotation terms from ``fusion_description`` (stored in
      ``sample.filters.fusion_description``) are matched against the ``desc``
      field of each call via a case-insensitive regex ``$elemMatch``.

    * **Gene filter** – ``gene1`` or ``gene2`` must appear in ``filter_genes``
      (the union of gene symbols from all selected fusion lists).
      Applied at the fusion-document level via a top-level ``$or``.
    """
    if assay_group not in ["fusion", "fusionrna", "wts"]:
        return {"SAMPLE_ID": settings["id"]}  # No filters for non-fusion assays

    min_spanning_reads = _coerce_nonnegative_int(settings.get("min_spanning_reads"), default=0)
    min_spanning_pairs = _coerce_nonnegative_int(settings.get("min_spanning_pairs"), default=0)

    call_match: Dict[str, Any] = {}

    # --- Effect filter ---
    effects = settings.get("fusion_effects") or []
    callers = settings.get("fusion_callers") or []
    if effects:
        call_match["effect"] = {"$in": effects}

    # --- Desc filter ---
    desc_patterns = fusion_annotation_filters(settings)

    # --- Caller-aware support thresholds ---
    # Arriba calls commonly have spanpairs=0, so pair threshold must not suppress
    # Arriba-only results when Arriba is selected.
    if callers:
        caller_clauses = []
        for caller in callers:
            clause: Dict[str, Any] = {"caller": caller}
            if min_spanning_reads > 0:
                clause["spanreads"] = {"$gte": min_spanning_reads}
            if min_spanning_pairs > 0 and caller != "arriba":
                clause["spanpairs"] = {"$gte": min_spanning_pairs}
            caller_clauses.append(clause)

        if caller_clauses:
            call_match["$or"] = caller_clauses
    else:

        if min_spanning_reads > 0:
            call_match["spanreads"] = {"$gte": min_spanning_reads}
        if min_spanning_pairs > 0:
            call_match["spanpairs"] = {"$gte": min_spanning_pairs}

    query: Dict[str, Any] = {"SAMPLE_ID": settings["id"]}
    if call_match:
        query["calls"] = {"$elemMatch": call_match}

    # Desc filter: dot-notation checks any call element, independent of the
    # caller/threshold $elemMatch above.
    if desc_patterns:
        query["calls.desc"] = {
            "$regex": "|".join(desc_patterns),
            "$options": "i",
        }

    # --- Gene filter ---
    # Show fusions where gene1 OR gene2 is present in the selected fusion-list genes.
    filter_genes = settings.get("filter_genes") or []
    if filter_genes:
        query["$or"] = [{"gene1": {"$in": filter_genes}}, {"gene2": {"$in": filter_genes}}]

    # Merge any additional optional filters into the base query.
    query.update(build_fusion_optional_filters())
    return query


def build_fusion_optional_filters() -> Dict[str, Any]:
    """
    Build optional fusion filters (only when values exist).
    Returns a dict that can be merged into the main query.
    """

    return {}
