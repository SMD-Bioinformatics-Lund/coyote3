"""Typed MongoDB predicate construction for DNA small-variant review."""

from __future__ import annotations

import re
from typing import Any

from api.config.clinical_query_policy import (
    CLINICAL_QUERY_POLICY,
    SnvQueryException,
    SnvQueryPolicy,
)


def _case_clause(settings: dict[str, Any]) -> dict[str, Any]:
    """Require configured evidence from the declared case genotype."""
    return {
        "GT": {
            "$elemMatch": {
                "type": "case",
                "AF": {
                    "$gte": float(settings["min_freq"]),
                    "$lte": float(settings["max_freq"]),
                },
                "DP": {"$gte": float(settings["min_depth"])},
                "VD": {"$gte": float(settings["min_alt_reads"])},
            }
        }
    }


def _case_or_untyped_clause(settings: dict[str, Any]) -> dict[str, Any]:
    """Accept case evidence where upstream data does not label genotype role."""
    evidence = {
        "AF": {
            "$gte": float(settings["min_freq"]),
            "$lte": float(settings["max_freq"]),
        },
        "DP": {"$gte": float(settings["min_depth"])},
        "VD": {"$gte": float(settings["min_alt_reads"])},
    }
    return {"$or": [_case_clause(settings), {"GT": {"$elemMatch": evidence}}]}


def _control_clause(settings: dict[str, Any]) -> dict[str, Any]:
    """Require an eligible control when present; permit samples without one."""
    return {
        "$or": [
            {
                "GT": {
                    "$elemMatch": {
                        "type": "control",
                        "AF": {"$lte": float(settings["max_control_freq"])},
                        "DP": {"$gte": float(settings["min_depth"])},
                    }
                }
            },
            {"GT": {"$not": {"$elemMatch": {"type": "control"}}}},
        ]
    }


def _population_frequency_clause(
    settings: dict[str, Any], policy: SnvQueryPolicy
) -> dict[str, Any]:
    """Require every available configured population frequency to be acceptable.

    Missing, null, and non-numeric values are retained because they cannot be
    safely compared with a numeric threshold. A finding is excluded when any
    configured numeric population source exceeds ``max_popfreq``.
    """
    threshold = float(settings["max_popfreq"])
    clauses = [
        {
            "$or": [
                {field: {"$lte": threshold, "$type": "number"}},
                {field: {"$exists": False}},
                {field: None},
                {field: {"$type": "string"}},
            ]
        }
        for field in policy.population_frequency_fields
    ]
    return {"$and": clauses}


def _consequence_terms_clause(terms: list[str]) -> dict[str, Any]:
    """Match terms aggregated from every VEP transcript at ingest time."""
    return {"consequence_terms": {"$in": terms}}


def _exception_clause(exception: SnvQueryException) -> dict[str, Any]:
    """Translate a validated exception into its restricted MongoDB predicate."""
    clauses: list[dict[str, Any]] = []
    if exception.genes:
        clauses.append({"INFO.selected_CSQ.SYMBOL": {"$in": list(exception.genes)}})
    if exception.consequence_terms:
        clauses.append({"consequence_terms": {"$in": list(exception.consequence_terms)}})
    if exception.filter_values:
        clauses.append({"FILTER": {"$in": list(exception.filter_values)}})
    if exception.chromosomes:
        clauses.append({"CHROM": {"$in": list(exception.chromosomes)}})
    if exception.position_min is not None or exception.position_max is not None:
        bounds: dict[str, int] = {}
        if exception.position_min is not None:
            bounds["$gte"] = exception.position_min
        if exception.position_max is not None:
            bounds["$lte"] = exception.position_max
        clauses.append({"POS": bounds})
    if exception.simple_ids:
        clauses.append({"simple_id": {"$in": list(exception.simple_ids)}})
    for field in exception.info_fields_present:
        clauses.append({f"INFO.{field}": {"$exists": True}})
    for field, value in sorted(exception.info_equals.items()):
        clauses.append({f"INFO.{field}": value})
    if exception.alt_regex:
        clauses.append({"ALT": re.compile(exception.alt_regex, re.IGNORECASE)})
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _consequence_admission_clause(
    *,
    policy: SnvQueryPolicy,
    assay_group: str,
    asp_id: str,
    subpanel_id: str,
    intent: str,
    terms: list[str],
) -> dict[str, Any]:
    """Allow aggregated terms or a configured clinically validated extension."""
    clauses = [_consequence_terms_clause(terms)]
    clauses.extend(
        _exception_clause(exception)
        for exception in policy.exceptions_for(
            assay_group=assay_group,
            asp_id=asp_id,
            subpanel_id=subpanel_id,
            intent=intent,
            mode="extend_consequence",
        )
    )
    return clauses[0] if len(clauses) == 1 else {"$or": clauses}


def _admission_clause(
    *, policy: SnvQueryPolicy, assay_group: str, asp_id: str, subpanel_id: str, intent: str
) -> dict[str, Any]:
    """Return explicit admission paths, or a predicate that can never match."""
    clauses = [
        _exception_clause(exception)
        for exception in policy.exceptions_for(
            assay_group=assay_group,
            asp_id=asp_id,
            subpanel_id=subpanel_id,
            intent=intent,
            mode="admit",
        )
    ]
    if not clauses:
        return {"_id": {"$exists": False}}
    return clauses[0] if len(clauses) == 1 else {"$or": clauses}


def _exclusion_clause(
    *, policy: SnvQueryPolicy, assay_group: str, asp_id: str, subpanel_id: str, intent: str
) -> dict[str, Any]:
    """Exclude typed clinical matches after the selected baseline is applied."""
    clauses = [
        _exception_clause(exception)
        for exception in policy.exceptions_for(
            assay_group=assay_group,
            asp_id=asp_id,
            subpanel_id=subpanel_id,
            intent=intent,
            mode="exclude",
        )
    ]
    return {"$nor": clauses} if clauses else {}


def build_query(
    assay_group: str,
    settings: dict[str, Any],
    *,
    intent: str = "somatic",
    policy: SnvQueryPolicy = CLINICAL_QUERY_POLICY.snv,
) -> dict[str, Any]:
    """Build an intent-specific SNV query from filters and released policy.

    ``settings`` carries sample identity plus resolved ``asp_id`` and
    ``subpanel_id``. They select configured exception scopes; they are never
    interpreted as data-store field paths or query operators.
    """
    normalized_group = str(assay_group or "").strip().lower()
    normalized_intent = str(intent or "somatic").strip().lower()
    if normalized_intent not in {"somatic", "germline"}:
        raise ValueError("intent must be somatic or germline")
    asp_id = str(settings.get("asp_id") or "").strip().lower()
    subpanel_id = str(settings.get("subpanel_id") or "base").strip().lower()
    baseline = policy.policy_for(assay_group=normalized_group, intent=normalized_intent)
    gene_position_scope = build_pos_genes_filter(settings)
    terms = list(settings.get("filter_conseq") or [])

    clauses: list[dict[str, Any]] = [gene_position_scope]
    if baseline == "paired":
        clauses.extend(
            [
                _case_clause(settings),
                _control_clause(settings),
                _population_frequency_clause(settings, policy),
                _consequence_admission_clause(
                    policy=policy,
                    assay_group=normalized_group,
                    asp_id=asp_id,
                    subpanel_id=subpanel_id,
                    intent=normalized_intent,
                    terms=terms,
                ),
            ]
        )
    elif baseline == "case_only":
        clauses.extend(
            [
                _case_or_untyped_clause(settings),
                _population_frequency_clause(settings, policy),
                _consequence_admission_clause(
                    policy=policy,
                    assay_group=normalized_group,
                    asp_id=asp_id,
                    subpanel_id=subpanel_id,
                    intent=normalized_intent,
                    terms=terms,
                ),
            ]
        )
    else:  # exception_only
        clauses.append(
            _admission_clause(
                policy=policy,
                assay_group=normalized_group,
                asp_id=asp_id,
                subpanel_id=subpanel_id,
                intent=normalized_intent,
            )
        )
    exclusion = _exclusion_clause(
        policy=policy,
        assay_group=normalized_group,
        asp_id=asp_id,
        subpanel_id=subpanel_id,
        intent=normalized_intent,
    )
    if exclusion:
        clauses.append(exclusion)
    return {"SAMPLE_ID": settings["id"], "$and": [clause for clause in clauses if clause]}


def build_pos_genes_filter(settings: dict[str, Any]) -> dict[str, Any]:
    """Build optional position, gene, false-positive, and irrelevant restrictions."""
    pos_list = settings.get("disp_pos", [])
    genes_list = settings.get("filter_genes", [])
    fp = settings.get("fp", "")
    irrelevant = settings.get("irrelevant", "")
    partial_query: dict[str, Any] = {}
    if pos_list:
        partial_query["POS"] = {"$in": pos_list}
    elif settings.get("restrict_to_genes") and not genes_list:
        partial_query["_id"] = {"$exists": False}
    elif genes_list:
        partial_query["genes"] = {"$in": genes_list}
    if fp:
        partial_query["fp"] = fp
    if irrelevant:
        partial_query["irrelevant"] = irrelevant
    return {"$and": [partial_query]} if partial_query else {}
