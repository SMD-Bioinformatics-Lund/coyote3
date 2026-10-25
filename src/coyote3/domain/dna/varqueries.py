"""Database-independent selection construction for DNA small-variant review."""

from __future__ import annotations

import re
from typing import Any

from coyote3.config.clinical_query_policy import (
    CLINICAL_QUERY_POLICY,
    SnvQueryException,
    SnvQueryPolicy,
)
from coyote3.domain.selection import (
    Criteria,
    Operator,
    RecordField,
    Selection,
    select,
)


def _case_clause(settings: dict[str, Any]) -> Selection:
    """Require configured evidence from the declared case genotype."""
    return select(
        {
            "GT": {
                Operator.ELEMENT: {
                    "type": "case",
                    "AF": {
                        Operator.AT_LEAST: float(settings["min_freq"]),
                        Operator.AT_MOST: float(settings["max_freq"]),
                    },
                    "DP": {Operator.AT_LEAST: float(settings["min_depth"])},
                    "VD": {Operator.AT_LEAST: float(settings["min_alt_reads"])},
                }
            }
        }
    )


def _case_or_untyped_clause(settings: dict[str, Any]) -> Selection:
    """Accept case evidence where upstream data does not label genotype role."""
    evidence = {
        "AF": {
            Operator.AT_LEAST: float(settings["min_freq"]),
            Operator.AT_MOST: float(settings["max_freq"]),
        },
        "DP": {Operator.AT_LEAST: float(settings["min_depth"])},
        "VD": {Operator.AT_LEAST: float(settings["min_alt_reads"])},
    }
    return select({Operator.ANY: [_case_clause(settings), {"GT": {Operator.ELEMENT: evidence}}]})


def _control_clause(settings: dict[str, Any]) -> Selection:
    """Require an eligible control when present; permit samples without one."""
    return select(
        {
            Operator.ANY: [
                {
                    "GT": {
                        Operator.ELEMENT: {
                            "type": "control",
                            "AF": {Operator.AT_MOST: float(settings["max_control_freq"])},
                            "DP": {Operator.AT_LEAST: float(settings["min_depth"])},
                        }
                    }
                },
                {"GT": {Operator.NOT: {Operator.ELEMENT: {"type": "control"}}}},
            ]
        }
    )


def _population_frequency_clause(settings: dict[str, Any], policy: SnvQueryPolicy) -> Selection:
    """Require every available configured population frequency to be acceptable.

    Missing, null, and non-numeric values are retained because they cannot be
    safely compared with a numeric threshold. A finding is excluded when any
    configured numeric population source exceeds ``max_popfreq``.
    """
    threshold = float(settings["max_popfreq"])
    clauses = [
        {
            Operator.ANY: [
                {field: {Operator.AT_MOST: threshold, Operator.VALUE_TYPE: "number"}},
                {field: {Operator.PRESENT: False}},
                {field: None},
                {field: {Operator.VALUE_TYPE: "string"}},
            ]
        }
        for field in policy.population_frequency_fields
    ]
    return select({Operator.ALL: clauses})


def _consequence_terms_clause(terms: list[str]) -> Selection:
    """Match terms aggregated from every VEP transcript at ingest time."""
    return select({"consequence_terms": {Operator.IN: terms}})


def _exception_clause(
    exception: SnvQueryException, filter_values: dict[str, Any] | None = None
) -> Selection:
    """Translate a validated exception into its restricted clinical selection.

    Args:
        exception: Validated SNV policy exception.
        filter_values: Prepared sample settings; required for reference operands.

    Returns:
        Clinical-record selection with references resolved for this sample.

    Raises:
        ValueError: A reference cannot resolve to a supported value.
    """
    clauses: list[Any] = []
    if exception.condition is not None:
        from coyote3.domain.query_conditions import compile_condition

        clauses.append(compile_condition(exception.condition, "snv", filter_values=filter_values))
    if exception.genes:
        clauses.append({"INFO.selected_CSQ.SYMBOL": {Operator.IN: list(exception.genes)}})
    if exception.consequence_terms:
        clauses.append({"consequence_terms": {Operator.IN: list(exception.consequence_terms)}})
    if exception.filter_values:
        clauses.append({"FILTER": {Operator.IN: list(exception.filter_values)}})
    if exception.chromosomes:
        clauses.append({"CHROM": {Operator.IN: list(exception.chromosomes)}})
    if exception.position_min is not None or exception.position_max is not None:
        bounds: dict[Operator, int] = {}
        if exception.position_min is not None:
            bounds[Operator.AT_LEAST] = exception.position_min
        if exception.position_max is not None:
            bounds[Operator.AT_MOST] = exception.position_max
        clauses.append({"POS": bounds})
    if exception.simple_ids:
        clauses.append({"simple_id": {Operator.IN: list(exception.simple_ids)}})
    for field in exception.info_fields_present:
        clauses.append({f"INFO.{field}": {Operator.PRESENT: True}})
    for field, value in sorted(exception.info_equals.items()):
        clauses.append({f"INFO.{field}": value})
    if exception.alt_regex:
        clauses.append({"ALT": re.compile(exception.alt_regex, re.IGNORECASE)})
    return select(clauses[0] if len(clauses) == 1 else {Operator.ALL: clauses})


def _consequence_admission_clause(
    *,
    policy: SnvQueryPolicy,
    assay_group: str,
    asp_id: str,
    diagnosis_id: str,
    intent: str,
    terms: list[str],
    filter_values: dict[str, Any] | None = None,
) -> Selection:
    """Allow aggregated terms or a configured clinically validated extension."""
    clauses = [_consequence_terms_clause(terms)]
    clauses.extend(
        _exception_clause(exception, filter_values)
        for exception in policy.exceptions_for(
            assay_group=assay_group,
            asp_id=asp_id,
            diagnosis_id=diagnosis_id,
            intent=intent,
            mode="extend_consequence",
        )
    )
    return select(clauses[0] if len(clauses) == 1 else {Operator.ANY: clauses})


def _admission_clause(
    *,
    policy: SnvQueryPolicy,
    assay_group: str,
    asp_id: str,
    diagnosis_id: str,
    intent: str,
    filter_values: dict[str, Any] | None = None,
) -> Selection:
    """Return explicit admission paths, or a predicate that can never match."""
    clauses = [
        _exception_clause(exception, filter_values)
        for exception in policy.exceptions_for(
            assay_group=assay_group,
            asp_id=asp_id,
            diagnosis_id=diagnosis_id,
            intent=intent,
            mode="admit",
        )
    ]
    if not clauses:
        return select({RecordField.IDENTITY: {Operator.PRESENT: False}})
    return select(clauses[0] if len(clauses) == 1 else {Operator.ANY: clauses})


def _exclusion_clause(
    *,
    policy: SnvQueryPolicy,
    assay_group: str,
    asp_id: str,
    diagnosis_id: str,
    intent: str,
    filter_values: dict[str, Any] | None = None,
) -> Selection:
    """Exclude typed clinical matches after the selected baseline is applied."""
    clauses = [
        _exception_clause(exception, filter_values)
        for exception in policy.exceptions_for(
            assay_group=assay_group,
            asp_id=asp_id,
            diagnosis_id=diagnosis_id,
            intent=intent,
            mode="exclude",
        )
    ]
    return select({Operator.NONE: clauses} if clauses else {})


def build_query(
    assay_group: str,
    settings: dict[str, Any],
    *,
    intent: str = "somatic",
    policy: SnvQueryPolicy = CLINICAL_QUERY_POLICY.snv,
) -> Selection:
    """Build an intent-specific SNV query from filters and released policy.

    ``settings`` carries sample identity plus resolved ``asp_id`` and
    ``diagnosis_id``. They select configured exception scopes; they are never
    interpreted as data-store field paths or query operators.
    Nonempty excluded-flag selections reject literal FILTER values after admission
    exceptions. An empty exclusion list does not restrict flags.
    """
    normalized_group = str(assay_group or "").strip().lower()
    normalized_intent = str(intent or "somatic").strip().lower()
    if normalized_intent not in {"somatic", "germline"}:
        raise ValueError("intent must be somatic or germline")
    asp_id = str(settings.get("asp_id") or "").strip().lower()
    diagnosis_id = str(settings.get("diagnosis_id") or "base").strip().lower()
    baseline = policy.policy_for(assay_group=normalized_group, intent=normalized_intent)
    gene_position_scope = build_pos_genes_filter(settings)
    terms = list(settings.get("filter_conseq") or [])

    clauses: list[Any] = [gene_position_scope]
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
                    diagnosis_id=diagnosis_id,
                    intent=normalized_intent,
                    terms=terms,
                    filter_values=settings,
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
                    diagnosis_id=diagnosis_id,
                    intent=normalized_intent,
                    terms=terms,
                    filter_values=settings,
                ),
            ]
        )
    else:  # exception_only
        clauses.append(
            _admission_clause(
                filter_values=settings,
                policy=policy,
                assay_group=normalized_group,
                asp_id=asp_id,
                diagnosis_id=diagnosis_id,
                intent=normalized_intent,
            )
        )
    if baseline != "exception_only" and policy.exceptions_for(
        assay_group=normalized_group,
        asp_id=asp_id,
        diagnosis_id=diagnosis_id,
        intent=normalized_intent,
        mode="admit",
    ):
        admission = _admission_clause(
            policy=policy,
            assay_group=normalized_group,
            asp_id=asp_id,
            diagnosis_id=diagnosis_id,
            intent=normalized_intent,
            filter_values=settings,
        )
        clauses = [gene_position_scope, {Operator.ANY: [{Operator.ALL: clauses[1:]}, admission]}]
    exclusion = _exclusion_clause(
        filter_values=settings,
        policy=policy,
        assay_group=normalized_group,
        asp_id=asp_id,
        diagnosis_id=diagnosis_id,
        intent=normalized_intent,
    )
    if exclusion:
        clauses.append(exclusion)
    if settings.get("exclude_flags"):
        clauses.append({"FILTER": {Operator.NOT_IN: list(settings["exclude_flags"])}})
    return select(
        {RecordField.SAMPLE: settings["id"], Operator.ALL: [clause for clause in clauses if clause]}
    )


def build_pos_genes_filter(settings: dict[str, Any]) -> Selection:
    """Build optional position, gene, false-positive, and irrelevant restrictions."""
    pos_list = settings.get("disp_pos", [])
    genes_list = settings.get("filter_genes", [])
    fp = settings.get("fp", "")
    irrelevant = settings.get("irrelevant", "")
    partial_query: Criteria = {}
    if pos_list:
        partial_query["POS"] = {Operator.IN: pos_list}
    elif settings.get("restrict_to_genes") and not genes_list:
        partial_query[RecordField.IDENTITY] = {Operator.PRESENT: False}
    elif genes_list:
        partial_query["genes"] = {Operator.IN: genes_list}
    if fp:
        partial_query["fp"] = fp
    if irrelevant:
        partial_query["irrelevant"] = irrelevant
    return select({Operator.ALL: [partial_query]} if partial_query else {})
