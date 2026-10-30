"""Render governed bulk annotation templates from reusable finding facts."""

from typing import Any

from coyote3.application.reporting.clinical_rules.evaluator import condition_matches, render_rule
from coyote3.contracts.schemas.clinical_rules import (
    BulkAnnotationPreviewRequest,
    BulkAnnotationPreviewResult,
    ClinicalRuleSetDoc,
)


def render_bulk_annotation(
    release: ClinicalRuleSetDoc,
    facts: BulkAnnotationPreviewRequest,
    *,
    diagnosis_id: str | None = None,
) -> BulkAnnotationPreviewResult:
    """Render the first enabled matching template for the requested tier.

    Args:
        release: Validated scoped rule version, published for persisted annotations.
        facts: Finding-level values, optional preview diagnosis and the explicitly chosen tier.
        diagnosis_id: Actual sample scope when a Base release supplies the template;
            None uses the release scope for synthetic preview.

    Returns:
        Matching rule identifier and text, or null values when no template matches.

    Raises:
        ValueError: A matched template has missing required values or empty output.

    Notes:
        No sample measurements, identifiers or patient information enter the scope.
        This function neither assigns tiers nor writes annotations.
    """
    scope: dict[str, Any] = {
        "sample": {
            "asp_id": release.scope.asp_id,
            "diagnosis_id": diagnosis_id or facts.diagnosis_id or release.scope.diagnosis_id,
        },
        "finding": facts.model_dump(),
    }
    for rule in sorted(release.bulk_annotation_rules, key=lambda item: item.order):
        if not rule.enabled or rule.tier != facts.tier:
            continue
        matched, missing = condition_matches(rule.condition, scope)
        if not matched or missing:
            continue
        text = render_rule(rule, scope=scope, terminology={}).strip()
        if not text:
            raise ValueError(f"Annotation rule '{rule.rule_id}' produced empty text")
        return BulkAnnotationPreviewResult(rule_id=rule.rule_id, text=text)
    return BulkAnnotationPreviewResult()
