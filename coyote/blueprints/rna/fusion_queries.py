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


from typing import Any, Dict, List, Optional


def build_fusion_query(assay_group: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a query to retrieve fusion data for a given sample.
    """
    if assay_group not in ["fusion", "fusionrna", "wts"]:
        return {"SAMPLE_ID": settings["id"]}  # No filters for non-fusion assays

    query = {
        "SAMPLE_ID": settings["id"],
        "calls": {
            "$elemMatch": {
                "spanreads": {"$gte": settings["min_spanning_reads"]},
                "spanpairs": {"$gte": settings["min_spanning_pairs"]},
            }
        },
    }

    # Merge optional filters into the base query
    query.update(build_fusion_optional_filters(settings))
    return query


def build_fusion_optional_filters(settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build optional fusion filters (only when values exist).
    Returns a dict that can be merged into the main query.
    """
    extra: Dict[str, Any] = {}

    # Optional $in filters
    effects = settings.get("fusion_effects") or []
    callers = settings.get("fusion_callers") or []

    if effects:
        extra["calls.effect"] = {"$in": effects}
    if callers:
        extra["calls.caller"] = {"$in": callers}

    # Optional fusion list filters -> merged as regex OR
    checked = set(settings.get("checked_fusionlists") or [])

    desc_patterns = {
        "fusionlist_FCknown": "known",
        "fusionlist_mitelman": "mitelman",
    }

    selected = [pat for key, pat in desc_patterns.items() if key in checked]
    if selected:
        extra["calls.desc"] = {"$regex": "|".join(selected), "$options": "i"}

    return extra
