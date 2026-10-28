"""Rank reusable interpretations without accepting broader context for reporting."""

from typing import Any


def select_sample_annotation_versions(
    annotations: list[dict[str, Any]], *, sample_id: object, report_references: set[str]
) -> list[dict[str, Any]]:
    """Prefer recorded sample history over reusable interpretations in each clinical scope.

    Args:
        annotations: Identity-matched, namespace-visible records in oldest-first order.
        sample_id: Current sample identifier, or None for a context-free lookup.
        report_references: Annotation IDs explicitly referenced by this sample's reports.

    Returns:
        Selected records in creation order. Unlinked inactive legacy versions carry
        legacy_fallback instead of being represented as verified sample history.
    """
    selected: dict[tuple[Any, ...], tuple[dict[str, Any], bool, int]] = {}
    for index, annotation in enumerate(annotations):
        key = tuple(
            annotation.get(field)
            for field in (
                "asp_group",
                "asp_id",
                "diagnosis_id",
                "namespace",
                "nomenclature",
                "gene",
                "gene1",
                "gene2",
                "transcript",
            )
        ) + ("class" if annotation.get("class") is not None else "text",)
        linked = bool(sample_id) and (
            str(annotation.get("source_sample_id") or "") == str(sample_id)
            or str(annotation.get("_id")) in report_references
        )
        previous = selected.get(key)
        if previous and previous[1] and not linked:
            continue
        selected[key] = (annotation, linked, index)
    result = []
    for annotation, linked, _index in sorted(selected.values(), key=lambda item: item[2]):
        if annotation.get("is_active", True):
            result.append(annotation)
        elif linked:
            result.append({**annotation, "historical_sample_match": True})
        elif not annotation.get("source_sample_id"):
            result.append({**annotation, "legacy_fallback": True})
    return result


def annotation_namespace(environment: str) -> str:
    """Map a sample environment to its stored interpretation namespace.

    Args:
        environment: Canonical production, development, testing or validation environment.

    Returns:
        Clinical for production; sandboxed for the three nonproduction environments.

    Raises:
        ValueError: The environment is absent or unrecognized.
    """
    if environment == "production":
        return "clinical"
    if environment in {"development", "testing", "validation"}:
        return "sandboxed"
    raise ValueError("A recognized sample environment is required for annotation scope")


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
        Match metadata. Only exact assay, diagnosis and group matches
        are effective. Other diagnoses remain contextual evidence, never fallback.
    """
    group = annotation.get("asp_group")
    distance = group_path.index(group) if group in group_path else None
    same_assay = bool(context.get("assay_id")) and annotation.get("asp_id") == context.get(
        "assay_id"
    )
    exact_diagnosis = annotation.get("diagnosis_id") == diagnosis
    broad_diagnosis = annotation.get("diagnosis_id") == "base"
    visible = annotation.get("namespace") == "clinical" or (
        context.get("environment") in {"development", "testing", "validation"}
        and annotation.get("namespace") == "sandboxed"
    )
    effective = visible and distance == 0 and same_assay and exact_diagnosis
    if effective:
        level, priority = "exact", 0
    elif distance == 0 and same_assay:
        level, priority = "same_assay", 1
    elif distance == 0:
        level, priority = "same_group", 2
    elif distance is not None:
        level, priority = "parent_group", 2 + distance
    else:
        level, priority = "other_group", 1000
    eligible = visible and distance is not None and (exact_diagnosis or broad_diagnosis)
    return {
        "match_level": level,
        "scope_priority": priority,
        "diagnosis_priority": 0 if exact_diagnosis else 1 if broad_diagnosis else 2,
        "inheritance_distance": distance,
        "fallback_eligible": eligible and not effective,
        "requires_retiering": not effective,
        "effective": effective,
    }
