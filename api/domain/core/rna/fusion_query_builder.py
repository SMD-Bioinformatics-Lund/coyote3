import re
from typing import Any, Dict

from api.config.clinical_query_policy import (
    CLINICAL_QUERY_POLICY,
    FindingQueryException,
    FindingQueryPolicy,
)
from api.config.clinical_vocabulary import CLINICAL_VOCABULARY
from api.domain.core.workflows.filter_normalization import coerce_nonnegative_int


def _fusion_exception_clause(exception: FindingQueryException) -> Dict[str, Any]:
    """Translate a validated RNA-fusion rule into stored fusion fields."""
    criteria = exception.criteria
    clauses: list[Dict[str, Any]] = []
    if criteria.get("genes"):
        genes = list(criteria["genes"])
        clauses.append({"$or": [{"gene1": {"$in": genes}}, {"gene2": {"$in": genes}}]})
    if criteria.get("gene_pairs"):
        pairs = []
        for value in criteria["gene_pairs"]:
            gene1, separator, gene2 = str(value).partition("--")
            if separator:
                pairs.extend(
                    [
                        {"gene1": gene1.upper(), "gene2": gene2.upper()},
                        {"gene1": gene2.upper(), "gene2": gene1.upper()},
                    ]
                )
        if pairs:
            clauses.append({"$or": pairs})
    call_match: Dict[str, Any] = {}
    if criteria.get("callers"):
        call_match["caller"] = {"$in": list(criteria["callers"])}
    if criteria.get("effects"):
        call_match["effect"] = {"$in": list(criteria["effects"])}
    if criteria.get("descriptions"):
        call_match["$or"] = [
            {
                "desc": {
                    "$regex": rf"(?:^|,\s*){re.escape(value)}(?:\s*,|$)",
                    "$options": "i",
                }
            }
            for value in criteria["descriptions"]
        ]
    if call_match:
        clauses.append({"calls": {"$elemMatch": call_match}})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def build_fusion_query(
    assay_group: str,
    settings: Dict[str, Any],
    *,
    policy: FindingQueryPolicy = CLINICAL_QUERY_POLICY.fusion,
) -> Dict[str, Any]:
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

    scope = {
        "assay_group": str(assay_group or "").strip().lower(),
        "asp_id": str(settings.get("asp_id") or "").strip().lower(),
        "subpanel_id": str(settings.get("subpanel_id") or "base").strip().lower(),
        "intent": str(settings.get("intent") or "somatic").strip().lower(),
    }
    admissions = [
        _fusion_exception_clause(exception)
        for exception in policy.exceptions_for(**scope, mode="admit")
    ]
    exclusions = [
        _fusion_exception_clause(exception)
        for exception in policy.exceptions_for(**scope, mode="exclude")
    ]
    baseline = {key: value for key, value in query.items() if key != "SAMPLE_ID"}
    final_clauses: list[Dict[str, Any]] = []
    if admissions and baseline:
        final_clauses.append({"$or": [baseline, *admissions]})
    elif baseline:
        final_clauses.append(baseline)
    if exclusions:
        final_clauses.append({"$nor": exclusions})
    if not final_clauses:
        return {"SAMPLE_ID": settings["id"]}
    if len(final_clauses) == 1:
        return {"SAMPLE_ID": settings["id"], **final_clauses[0]}
    return {"SAMPLE_ID": settings["id"], "$and": final_clauses}
