"""Deterministic evaluator for compiled clinical reporting rules."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from api.application.reporting.clinical_rules.facts import (
    PreparedFindingFacts,
    PreparedReportContext,
)
from api.application.reporting.clinical_rules.templating import clinical_template_environment
from api.contracts.schemas.clinical_rules import (
    ClinicalRuleCondition,
    ClinicalRuleEvaluation,
    ClinicalRuleFamily,
    ClinicalRuleOperator,
    ClinicalRuleReleaseDoc,
    ClinicalRuleReleaseRef,
    ClinicalRuleTraceEntry,
)


def _resolve_path(scope: Mapping[str, Any], path: str) -> tuple[Any, bool]:
    value: Any = scope
    for part in path.split("."):
        if isinstance(value, Mapping) and part in value:
            value = value[part]
            continue
        return None, False
    return value, True


def _condition_matches(
    condition: ClinicalRuleCondition, scope: Mapping[str, Any]
) -> tuple[bool, bool]:
    actual, exists = _resolve_path(scope, condition.fact)
    operator = condition.operator
    expected = condition.value
    if operator == ClinicalRuleOperator.EXISTS:
        return exists is bool(expected), exists
    if not exists:
        return False, False
    if operator == ClinicalRuleOperator.EQ:
        return actual == expected, True
    if operator == ClinicalRuleOperator.NE:
        return actual != expected, True
    if operator == ClinicalRuleOperator.IN:
        return actual in expected, True
    if operator == ClinicalRuleOperator.NOT_IN:
        return actual not in expected, True
    if operator == ClinicalRuleOperator.CONTAINS:
        return isinstance(actual, (Sequence, set, frozenset, str)) and expected in actual, True
    if operator == ClinicalRuleOperator.OVERLAPS:
        if not isinstance(actual, (Sequence, set, frozenset)) or isinstance(actual, str):
            return False, True
        if not isinstance(expected, (Sequence, set, frozenset)) or isinstance(expected, str):
            return False, True
        return bool(set(actual) & set(expected)), True
    try:
        if operator == ClinicalRuleOperator.GT:
            return actual > expected, True
        if operator == ClinicalRuleOperator.GTE:
            return actual >= expected, True
        if operator == ClinicalRuleOperator.LT:
            return actual < expected, True
        if operator == ClinicalRuleOperator.LTE:
            return actual <= expected, True
    except TypeError:
        return False, True
    return False, True


class ClinicalRuleEvaluator:
    """Evaluate a published release against one prepared report context."""

    def __init__(self) -> None:
        self.environment = clinical_template_environment()

    def evaluate(
        self,
        context: PreparedReportContext,
        release: ClinicalRuleReleaseDoc,
    ) -> ClinicalRuleEvaluation:
        """Evaluate ordered rules and return rendered sections plus trace."""
        release_ref = ClinicalRuleReleaseRef(
            release_id=release.id_,
            rule_set_id=release.rule_set_id,
            version=release.version,
            content_hash=release.content_hash,
        )
        sections: dict[str, list[str]] = {}
        trace: list[ClinicalRuleTraceEntry] = []
        rules = sorted(
            release.source.rules,
            key=lambda rule: (list(ClinicalRuleFamily).index(rule.family), rule.priority),
        )

        for family in ClinicalRuleFamily:
            family_rules = [rule for rule in rules if rule.family == family]
            candidates: list[PreparedFindingFacts | None]
            candidates = context.findings if family == ClinicalRuleFamily.FINDING_TEXT else [None]
            for finding_index, finding in enumerate(candidates):
                for rule in family_rules:
                    scope = context.evaluation_scope(finding)
                    missing_facts: list[str] = []
                    matched = True
                    for condition in rule.when:
                        condition_match, exists = _condition_matches(condition, scope)
                        if not exists:
                            missing_facts.append(condition.fact)
                        if not condition_match:
                            matched = False
                    rendered_text = None
                    if matched:
                        rendered_text = (
                            self.environment.from_string(rule.template).render(**scope).strip()
                        )
                        if rendered_text:
                            sections.setdefault(rule.section, []).append(rendered_text)
                    trace.append(
                        ClinicalRuleTraceEntry(
                            rule_id=rule.rule_id,
                            family=rule.family,
                            section=rule.section,
                            matched=matched,
                            finding_index=(
                                finding_index if family == ClinicalRuleFamily.FINDING_TEXT else None
                            ),
                            missing_facts=missing_facts,
                            rendered_text=rendered_text,
                        )
                    )
                    if matched and rule.stop:
                        break

        return ClinicalRuleEvaluation(release=release_ref, sections=sections, trace=trace)
