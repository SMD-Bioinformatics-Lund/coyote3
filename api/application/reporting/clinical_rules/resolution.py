"""Select a published clinical rule release by report scope."""

from typing import Any

from api.application.reporting.clinical_rules.validation import content_hash
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc


def load_compiled_rule_set(configuration: dict[str, Any]) -> ClinicalRuleSetDoc:
    """Verify the exact report-rule document captured in an ASPC release.

    Args:
        configuration: Pinned ASPC document with its captured clinical_rule_release.

    Returns:
        Original published rule content, independent of subsequent source retirement.

    Raises:
        ValueError: Content is missing, modified, unpublished or outside the release scope.
    """
    snapshot = configuration.get("clinical_rule_release")
    if not isinstance(snapshot, dict):
        raise ValueError("The configuration has no compiled clinical rule release")
    rule_set = ClinicalRuleSetDoc.model_validate(snapshot)
    if rule_set.content_hash != content_hash(rule_set):
        raise ValueError("Compiled clinical rule-set content failed integrity validation")
    if (
        rule_set.status != "published"
        or not rule_set.active
        or rule_set.scope.asp_id != configuration.get("asp_id")
        or rule_set.scope.analyte != configuration.get("asp_category")
        or rule_set.scope.language != configuration.get("reporting", {}).get("language", "sv")
        or rule_set.scope.diagnosis_id not in {configuration.get("diagnosis_id"), "base"}
    ):
        raise ValueError("Compiled clinical rule-set scope does not match its configuration")
    return rule_set


def resolve_published_rule_set(
    repository: Any, *, asp_id: str, diagnosis_id: str, analyte: str, language: str
) -> ClinicalRuleSetDoc:
    """Select an exact scope or its assay Base release, without crossing languages.

    Args:
        repository: Clinical rule repository exposing active releases for an assay.
        asp_id: Exact assay identifier.
        diagnosis_id: Sample interpretation scope; empty means Base.
        analyte: DNA or RNA, expressed in lowercase.
        language: Reporting language tag.

    Returns:
        The sole active published release at the most specific available scope.

    Raises:
        ValueError: No release matches, a selected scope is ambiguous, or stored
            rule content violates its contract or hash. An invalid exact release
            never causes a silent switch to Base.
    """
    scope = diagnosis_id or "base"
    candidates = [
        row
        for row in repository.list_active_for_assay(
            asp_id, diagnosis_id=scope, analyte=analyte, language=language
        )
        if row.get("active") is True
        and row.get("status") == "published"
        and row.get("scope", {}).get("asp_id") == asp_id
        and row.get("scope", {}).get("analyte") == analyte
        and row.get("scope", {}).get("language") == language
    ]
    for selected in dict.fromkeys((scope, "base")):
        matches = [row for row in candidates if row["scope"].get("diagnosis_id") == selected]
        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous published clinical rules for {asp_id}/{selected}/{analyte}/{language}"
            )
        if matches:
            rule_set = ClinicalRuleSetDoc.model_validate(matches[0])
            if rule_set.content_hash != content_hash(rule_set):
                raise ValueError("Published clinical rule-set content failed integrity validation")
            return rule_set
    raise ValueError(
        f"No active published clinical rule set for {asp_id}/{scope}/{analyte}/{language} or assay Base"
    )
