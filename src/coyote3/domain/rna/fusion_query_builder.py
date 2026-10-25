"""Build sample-scoped RNA fusion predicates from filters and query policy."""

import re
from typing import Any, Dict

from coyote3.config.clinical_query_policy import (
    CLINICAL_QUERY_POLICY,
    FindingQueryException,
    FindingQueryPolicy,
)
from coyote3.config.clinical_vocabulary import CLINICAL_VOCABULARY
from coyote3.domain.filtering.normalization import coerce_nonnegative_int
from coyote3.domain.selection import Criteria, Operator, RecordField, Selection, select


def _fusion_exception_clause(
    exception: FindingQueryException, filter_values: dict[str, Any] | None = None
) -> Selection:
    """Translate a validated RNA-fusion rule into stored fusion fields.

    Args:
        exception: Validated fusion policy exception.
        filter_values: Prepared sample settings; required for reference operands.

    Returns:
        Clinical-record selection with references resolved for this sample.

    Raises:
        ValueError: A reference cannot resolve to a supported value.
    """
    criteria = exception.criteria
    clauses: list[Any] = []
    if criteria.get("condition") is not None:
        from coyote3.domain.query_conditions import compile_condition

        clauses.append(
            compile_condition(criteria["condition"], "fusion", filter_values=filter_values)
        )
    if criteria.get("genes"):
        genes = list(criteria["genes"])
        clauses.append(
            {Operator.ANY: [{"gene1": {Operator.IN: genes}}, {"gene2": {Operator.IN: genes}}]}
        )
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
            clauses.append({Operator.ANY: pairs})
    call_match: Criteria = {}
    if criteria.get("callers"):
        call_match["caller"] = {Operator.IN: list(criteria["callers"])}
    if criteria.get("effects"):
        call_match["effect"] = {Operator.IN: list(criteria["effects"])}
    if criteria.get("descriptions"):
        call_match[Operator.ANY] = [
            {
                "desc": {
                    Operator.PATTERN: rf"(?:^|,\s*){re.escape(value)}(?:\s*,|$)",
                    Operator.PATTERN_OPTIONS: "i",
                }
            }
            for value in criteria["descriptions"]
        ]
    if call_match:
        clauses.append({"calls": {Operator.ELEMENT: call_match}})
    return select(clauses[0] if len(clauses) == 1 else {Operator.ALL: clauses})


def build_fusion_query(
    assay_group: str,
    settings: Dict[str, Any],
    *,
    policy: FindingQueryPolicy = CLINICAL_QUERY_POLICY.fusion,
) -> Selection:
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

    call_match: Criteria = {}

    effects = settings.get("fusion_effects") or []
    callers = CLINICAL_VOCABULARY.normalize_fusion_callers(settings.get("fusion_callers") or [])
    descriptions = [
        str(value).strip()
        for value in settings.get("fusion_descriptions") or []
        if str(value).strip()
    ]
    effect_set = {str(effect).strip().lower() for effect in effects if str(effect).strip()}
    if effect_set == {"in-frame"}:
        call_match["effect"] = {Operator.PATTERN: r"^in-frame$", Operator.PATTERN_OPTIONS: "i"}
    elif effect_set == {"out-of-frame"}:
        call_match["effect"] = {
            Operator.PATTERN: r"^(?!in-frame$).+",
            Operator.PATTERN_OPTIONS: "i",
        }

    if callers:
        caller_clauses = []
        for caller in callers:
            clause: Criteria = {"caller": caller}
            if min_spanning_reads > 0:
                clause["spanreads"] = {Operator.AT_LEAST: min_spanning_reads}
            if min_spanning_pairs > 0 and caller != "arriba":
                clause["spanpairs"] = {Operator.AT_LEAST: min_spanning_pairs}
            caller_clauses.append(clause)

        if caller_clauses:
            call_match[Operator.ANY] = caller_clauses
    else:
        if min_spanning_reads > 0:
            call_match["spanreads"] = {Operator.AT_LEAST: min_spanning_reads}
        if min_spanning_pairs > 0:
            call_match["spanpairs"] = {Operator.AT_LEAST: min_spanning_pairs}

    if descriptions:
        description_clauses = [
            {
                "desc": {
                    Operator.PATTERN: rf"(?:^|,\s*){re.escape(description)}(?:\s*,|$)",
                    Operator.PATTERN_OPTIONS: "i",
                }
            }
            for description in descriptions
        ]
        if Operator.ANY in call_match:
            caller_clauses = call_match.pop(Operator.ANY)
            call_match[Operator.ALL] = [
                {Operator.ANY: caller_clauses},
                {Operator.ANY: description_clauses},
            ]
        else:
            call_match[Operator.ANY] = description_clauses

    query: Criteria = {RecordField.SAMPLE: settings["id"]}
    if call_match:
        query["calls"] = {Operator.ELEMENT: call_match}

    filter_genes = settings.get("filter_genes") or []
    if settings.get("restrict_to_genes") and not filter_genes:
        query[RecordField.IDENTITY] = {Operator.PRESENT: False}
    elif filter_genes:
        query[Operator.ANY] = [
            {"gene1": {Operator.IN: filter_genes}},
            {"gene2": {Operator.IN: filter_genes}},
        ]

    scope = {
        "assay_group": str(assay_group or "").strip().lower(),
        "asp_id": str(settings.get("asp_id") or "").strip().lower(),
        "diagnosis_id": str(settings.get("diagnosis_id") or "base").strip().lower(),
        "intent": str(settings.get("intent") or "somatic").strip().lower(),
    }
    admissions = [
        _fusion_exception_clause(exception, settings)
        for exception in policy.exceptions_for(**scope, mode="admit")
    ]
    exclusions = [
        _fusion_exception_clause(exception, settings)
        for exception in policy.exceptions_for(**scope, mode="exclude")
    ]
    baseline = {key: value for key, value in query.items() if key != RecordField.SAMPLE}
    final_clauses: list[Any] = []
    if admissions and baseline:
        final_clauses.append({Operator.ANY: [baseline, *admissions]})
    elif baseline:
        final_clauses.append(baseline)
    if exclusions:
        final_clauses.append({Operator.NONE: exclusions})
    if not final_clauses:
        return select({RecordField.SAMPLE: settings["id"]})
    if len(final_clauses) == 1:
        return select({RecordField.SAMPLE: settings["id"], **final_clauses[0]})
    return select({RecordField.SAMPLE: settings["id"], Operator.ALL: final_clauses})
