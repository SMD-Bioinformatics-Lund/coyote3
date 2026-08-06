import re
from typing import Any, Dict

from api.config.clinical_vocabulary import CLINICAL_VOCABULARY
from api.domain.core.workflows.filter_normalization import coerce_nonnegative_int


def build_fusion_query(assay_group: str, settings: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a query to retrieve fusion data for a given RNA sample.

    The calling workflow has already established that fusion analysis is
    enabled for the sample. Assay group is retained in the public signature
    for workflow compatibility, but it must not suppress configured filters:
    targeted RNA panels and WTS samples use the same fusion filter contract.
    """
    _ = assay_group

    min_spanning_reads = coerce_nonnegative_int(settings.get("min_spanning_reads"), default=0)
    min_spanning_pairs = coerce_nonnegative_int(settings.get("min_spanning_pairs"), default=0)

    call_match: Dict[str, Any] = {}

    effects = settings.get("fusion_effects") or []
    callers = CLINICAL_VOCABULARY.normalize_fusion_callers(settings.get("fusion_callers") or [])
    descriptions = [
        str(value).strip()
        for value in settings.get("fusion_descriptions") or []
        if str(value).strip()
    ]
    effect_set = {str(effect).strip().lower() for effect in effects if str(effect).strip()}
    if effect_set == {"in-frame"}:
        call_match["effect"] = {"$regex": r"^in-frame$", "$options": "i"}
    elif effect_set == {"out-of-frame"}:
        call_match["effect"] = {
            "$regex": r"^(?!in-frame$).+",
            "$options": "i",
        }

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

    if descriptions:
        description_clauses = [
            {
                "desc": {
                    "$regex": rf"(?:^|,\s*){re.escape(description)}(?:\s*,|$)",
                    "$options": "i",
                }
            }
            for description in descriptions
        ]
        if "$or" in call_match:
            caller_clauses = call_match.pop("$or")
            call_match["$and"] = [
                {"$or": caller_clauses},
                {"$or": description_clauses},
            ]
        else:
            call_match["$or"] = description_clauses

    query: Dict[str, Any] = {"SAMPLE_ID": settings["id"]}
    if call_match:
        query["calls"] = {"$elemMatch": call_match}

    filter_genes = settings.get("filter_genes") or []
    if settings.get("restrict_to_genes") and not filter_genes:
        query["_id"] = {"$exists": False}
    elif filter_genes:
        query["$or"] = [{"gene1": {"$in": filter_genes}}, {"gene2": {"$in": filter_genes}}]

    return query
