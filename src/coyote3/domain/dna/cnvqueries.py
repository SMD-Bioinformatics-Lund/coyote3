"""Service-level DNA CNV query builders."""

from __future__ import annotations

from typing import Any

from coyote3.config.clinical_query_policy import (
    CLINICAL_QUERY_POLICY,
    FindingQueryException,
    FindingQueryPolicy,
)
from coyote3.domain.selection import (
    Operator,
    RecordField,
    Selection,
    select,
)


def _cnv_exception_clause(
    exception: FindingQueryException, filter_values: dict[str, Any] | None = None
) -> Selection:
    """Translate a validated CNV rule into the fixed CNV document vocabulary.

    Args:
        exception: Validated CNV policy exception.
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

        clauses.append(compile_condition(criteria["condition"], "cnv", filter_values=filter_values))
    if criteria.get("genes"):
        genes = list(criteria["genes"])
        clauses.append(
            {
                Operator.ANY: [
                    {"genes.gene": {Operator.IN: genes}},
                    {"panel_gene": {Operator.IN: genes}},
                ]
            }
        )
    if criteria.get("callers"):
        clauses.append({"callers": {Operator.IN: list(criteria["callers"])}})
    if criteria.get("effects"):
        clauses.append({"type": {Operator.IN: list(criteria["effects"])}})
    if criteria.get("chromosomes"):
        clauses.append({"chr": {Operator.IN: list(criteria["chromosomes"])}})
    if criteria.get("size_min") is not None or criteria.get("size_max") is not None:
        bounds: dict[Operator, int] = {}
        if criteria.get("size_min") is not None:
            bounds[Operator.AT_LEAST] = criteria["size_min"]
        if criteria.get("size_max") is not None:
            bounds[Operator.AT_MOST] = criteria["size_max"]
        clauses.append({"size": bounds})
    return select(clauses[0] if len(clauses) == 1 else {Operator.ALL: clauses})


def include_normal_cnvs(sample: dict[str, Any], assay_panel: dict[str, Any] | None = None) -> bool:
    """Return whether the sample scope includes normal/control CNV records.

    Targeted panels review tumour calls separately from records marked as
    normal. Whole-genome analysis retains both in the same review table, as in
    the whole-genome workflow. Group identifiers never select a query strategy.
    """
    panel = assay_panel or {}
    asp_family = str(sample.get("asp_family") or "").strip().lower()
    panel_family = str(panel.get("asp_family") or "").strip().lower()
    return asp_family == "wgs" or panel_family == "wgs"


def build_cnv_query(
    sample_id: str,
    filters: dict[str, Any],
    *,
    include_normal: bool = False,
    policy: FindingQueryPolicy = CLINICAL_QUERY_POLICY.cnv,
) -> Selection:
    """Build a CNV query for a sample based on configured filter criteria."""
    clauses: list[Any] = []

    if not include_normal:
        clauses.append(
            {
                Operator.ANY: [
                    {"NORMAL": {Operator.NOT_EQUAL: 1}},
                    {"NORMAL": {Operator.PRESENT: False}},
                ]
            }
        )

    if filters:
        ratio_outside_thresholds = {
            Operator.ANY: [
                {"ratio": {Operator.LESS: filters["cnv_loss_cutoff"]}},
                {"ratio": {Operator.GREATER: filters["cnv_gain_cutoff"]}},
            ]
        }
        size_within_thresholds = {
            Operator.ALL: [
                {"size": {Operator.GREATER: filters["min_cnv_size"]}},
                {"size": {Operator.LESS: filters["max_cnv_size"]}},
            ]
        }
        high_level_amplification = {"ratio": {Operator.GREATER: 3}}
        missing_ratio = {
            Operator.ANY: [
                {"ratio": None},
                {"ratio": {Operator.PRESENT: False}},
            ]
        }
        structural_read_evidence = {
            Operator.ANY: [
                {"SR": {Operator.PRESENT: True, Operator.NOT_IN: [None, "", []]}},
                {"PR": {Operator.PRESENT: True, Operator.NOT_IN: [None, "", []]}},
            ]
        }

        # Ratio callers use copy-number and size thresholds. Structural callers
        # such as Manta have no ratio and are admitted by split/paired-read
        # evidence instead; applying ratio or minimum-size filters to those
        # records would silently remove valid breakpoints.
        clauses.append(
            {
                Operator.ANY: [
                    {
                        Operator.ALL: [
                            ratio_outside_thresholds,
                            {
                                Operator.ANY: [
                                    size_within_thresholds,
                                    high_level_amplification,
                                ]
                            },
                        ]
                    },
                    {
                        Operator.ALL: [
                            missing_ratio,
                            structural_read_evidence,
                        ]
                    },
                ]
            }
        )
        if filters.get("restrict_to_genes") and not filters.get("filter_genes"):
            clauses.append({RecordField.IDENTITY: {Operator.PRESENT: False}})
        elif filters.get("filter_genes"):
            clauses.append(
                {
                    Operator.ANY: [
                        {"genes.gene": {Operator.IN: filters.get("filter_genes", [])}},
                        {"panel_gene": {Operator.IN: filters.get("filter_genes", [])}},
                    ]
                }
            )

    scope = {
        "assay_group": str(filters.get("assay_group") or "").strip().lower(),
        "asp_id": str(filters.get("asp_id") or "").strip().lower(),
        "diagnosis_id": str(filters.get("diagnosis_id") or "base").strip().lower(),
        "intent": str(filters.get("intent") or "somatic").strip().lower(),
    }
    admissions = [
        _cnv_exception_clause(exception, filters)
        for exception in policy.exceptions_for(**scope, mode="admit")
    ]
    exclusions = [
        _cnv_exception_clause(exception, filters)
        for exception in policy.exceptions_for(**scope, mode="exclude")
    ]
    if admissions and clauses:
        baseline = {Operator.ALL: clauses}
        clauses = [{Operator.ANY: [baseline, *admissions]}]
    if exclusions:
        clauses.append({Operator.NONE: exclusions})
    if not clauses:
        return select({RecordField.SAMPLE: sample_id})
    return select({RecordField.SAMPLE: sample_id, Operator.ALL: clauses})
