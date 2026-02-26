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

from typing import Any, Dict

from coyote.services.workflow.filter_normalization import coerce_nonnegative_int


def build_fusion_query(assay_group: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a query to retrieve fusion data for a given sample.
    """
    if assay_group not in ["fusion", "fusionrna", "wts"]:
        return {"SAMPLE_ID": settings["id"]}  # No filters for non-fusion assays

    min_spanning_reads = coerce_nonnegative_int(settings.get("min_spanning_reads"), default=0)
    min_spanning_pairs = coerce_nonnegative_int(settings.get("min_spanning_pairs"), default=0)

    call_match: Dict[str, Any] = {}

    effects = settings.get("fusion_effects") or []
    callers = settings.get("fusion_callers") or []
    if effects:
        call_match["effect"] = {"$in": effects}

    checked = set(settings.get("checked_fusionlists") or [])
    selected_desc_patterns = []
    if "FCknown" in checked:
        selected_desc_patterns.append("known")
    if "mitelman" in checked:
        selected_desc_patterns.append("mitelman")
    if selected_desc_patterns:
        call_match["desc"] = {"$regex": "|".join(selected_desc_patterns), "$options": "i"}

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

    filter_genes = settings.get("filter_genes") or []
    if filter_genes:
        query["$or"] = [{"gene1": {"$in": filter_genes}}, {"gene2": {"$in": filter_genes}}]

    query.update(build_fusion_optional_filters(settings))
    return query


def build_fusion_optional_filters(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build optional fusion filters (only when values exist).
    Returns a dict that can be merged into the main query.
    """
    return {}
