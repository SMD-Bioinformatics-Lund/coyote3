"""Rank reusable interpretations without accepting broader context for reporting."""

from typing import Any


def annotation_scope_match(
    annotation: dict[str, Any], *, group_path: list[str], diagnosis: str, context: dict[str, Any]
) -> dict[str, Any]:
    """Describe specificity and confirmation needs for an identity-matched annotation.

    Args:
        annotation: Interpretation already matched by finding identity and visibility.
        group_path: Sample group followed by its nearest-to-farthest ancestors.
        diagnosis: Sample diagnosis, including the explicit base scope.
        context: Resolved sample assay and environment.

    Returns:
        Match metadata. Only exact assay, diagnosis, group and environment matches
        are effective. Other diagnoses remain contextual evidence, never fallback.
    """
    source = annotation.get("resource_context") or {}
    group = annotation.get("assay")
    distance = group_path.index(group) if group in group_path else None
    same_assay = bool(context.get("assay_id")) and source.get("assay_id") == context.get("assay_id")
    same_environment = source.get("environment") == context.get("environment")
    exact_diagnosis = annotation.get("diagnosis") == diagnosis
    broad_diagnosis = annotation.get("diagnosis") == "base"
    effective = distance == 0 and same_assay and same_environment and exact_diagnosis
    if effective:
        level, priority = "exact", 0
    elif distance == 0 and same_assay and same_environment:
        level, priority = "same_assay", 1
    elif distance == 0:
        level, priority = "same_group", 2
    elif distance is not None:
        level, priority = "parent_group", 2 + distance
    else:
        level, priority = "other_group", 1000
    eligible = distance is not None and (exact_diagnosis or broad_diagnosis)
    return {
        "match_level": level,
        "scope_priority": priority,
        "diagnosis_priority": 0 if exact_diagnosis else 1 if broad_diagnosis else 2,
        "inheritance_distance": distance,
        "fallback_eligible": eligible and not effective,
        "requires_retiering": not effective,
        "effective": effective,
    }
