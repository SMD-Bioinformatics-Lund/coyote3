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


def build_fusion_query(assay_group: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a query to retrieve fusion data for a given sample.
    """
    if assay_group not in ["fusion", "fusionrna", "wts"]:
        return {"SAMPLE_ID": settings["id"]}  # No filters for non-fusion assays

    call_match: Dict[str, Any] = {
        "spanreads": {"$gte": settings["min_spanning_reads"]},
        "spanpairs": {"$gte": settings["min_spanning_pairs"]},
    }

    # Optional call-level filters should be matched on the same call entry.
    effects = settings.get("fusion_effects") or []
    callers = settings.get("fusion_callers") or []
    if effects:
        call_match["effect"] = {"$in": effects}
    if callers:
        call_match["caller"] = {"$in": callers}

    # Optional preset list filters (desc tags)
    checked = set(settings.get("checked_fusionlists") or [])
    selected_desc_patterns = []
    if "FCknown" in checked:
        selected_desc_patterns.append("known")
    if "mitelman" in checked:
        selected_desc_patterns.append("mitelman")
    if selected_desc_patterns:
        call_match["desc"] = {"$regex": "|".join(selected_desc_patterns), "$options": "i"}

    query = {"SAMPLE_ID": settings["id"], "calls": {"$elemMatch": call_match}}

    # Optional fusion-gene filter generated from selected In Silico Gene Lists.
    filter_genes = settings.get("filter_genes") or []
    if filter_genes:
        query["$or"] = [{"gene1": {"$in": filter_genes}}, {"gene2": {"$in": filter_genes}}]

    # Merge any additional optional filters into the base query.
    query.update(build_fusion_optional_filters(settings))
    return query


def build_fusion_optional_filters(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build optional fusion filters (only when values exist).
    Returns a dict that can be merged into the main query.
    """
    extra: Dict[str, Any] = {}

    return extra
