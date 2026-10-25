"""Select a published clinical rule release by report scope."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from coyote3.application.reporting.clinical_rules.validation import content_hash
from coyote3.contracts.schemas.clinical_rules import ClinicalRuleSetDoc

_report_rules: ContextVar[dict[str, dict[str, Any]] | None] = ContextVar(
    "report_clinical_rules", default=None
)


@contextmanager
def capture_clinical_rules() -> Iterator[dict[str, dict[str, Any]]]:
    """Capture exact rule documents and profile sources used during one report build.

    Yields:
        Resolved rule content and source provenance, isolated from concurrent requests.
    """
    rules: dict[str, dict[str, Any]] = {}
    token = _report_rules.set(rules)
    try:
        yield rules
    finally:
        _report_rules.reset(token)


def record_clinical_rules(key: str, document: dict[str, Any]) -> None:
    """Retain a resolved rule and its source documents in the active report receipt.

    Args:
        key: Complete scope identity for the selected publication.
        document: Effective rule set, base publication and applied profile provenance.
    """
    rules = _report_rules.get()
    if rules is not None:
        rules[key] = document


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
