"""Structural and semantic validation for canonical clinical rule sets."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from api.application.reporting.clinical_rules.registry import validate_fact_path
from api.contracts.schemas.clinical_rules import (
    ClinicalCondition,
    ClinicalFactOutput,
    ClinicalListOutput,
    ClinicalMessageOutput,
    ClinicalNumberOutput,
    ClinicalRuleAll,
    ClinicalRuleAny,
    ClinicalRuleCollectionMatch,
    ClinicalRuleNot,
    ClinicalRulePredicate,
    ClinicalRuleSetDoc,
    ClinicalRuleValidationResult,
)

ENGINE_VERSION = 1
MAX_CONDITION_DEPTH = 6


def canonical_content(document: ClinicalRuleSetDoc) -> dict[str, Any]:
    """Return only immutable clinical content used for provenance hashing."""
    return document.model_dump(
        mode="json",
        include={
            "rule_set_id",
            "schema_version",
            "content_version",
            "scope",
            "name",
            "minimum_engine_version",
            "analysis_declarations",
            "terminology",
            "blocks",
            "test_cases",
            "references",
        },
        exclude_none=True,
    )


def content_hash(document: ClinicalRuleSetDoc) -> str:
    """Hash canonical clinical content with stable JSON key ordering.

    Args:
        document: Rule set whose canonical fields exclude lifecycle metadata.

    Returns:
        Hexadecimal SHA-256 digest of compact UTF-8 JSON.
    """
    payload = json.dumps(
        canonical_content(document), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_condition(
    condition: ClinicalCondition,
    *,
    scope: str,
    depth: int,
    errors: list[str],
) -> None:
    """Collect invalid fact, operator, scope, and nesting errors recursively.

    Args:
        condition: Condition subtree to inspect.
        scope: Evaluation mode used for fact availability checks.
        depth: Current nesting level; callers start root conditions at one.
        errors: Mutable list to which validation messages are appended.
    """
    if depth > MAX_CONDITION_DEPTH:
        errors.append(f"Condition nesting exceeds {MAX_CONDITION_DEPTH} levels")
        return
    if isinstance(condition, ClinicalRulePredicate):
        try:
            fact = validate_fact_path(condition.fact, scope=scope)
            if condition.operator.value not in fact.operators:
                errors.append(
                    f"Operator '{condition.operator.value}' is invalid for fact '{condition.fact}'"
                )
        except ValueError as exc:
            errors.append(str(exc))
        return
    if isinstance(condition, (ClinicalRuleAll, ClinicalRuleAny)):
        for child in condition.children:
            _validate_condition(child, scope=scope, depth=depth + 1, errors=errors)
        return
    if isinstance(condition, ClinicalRuleNot):
        _validate_condition(condition.child, scope=scope, depth=depth + 1, errors=errors)
        return
    if isinstance(condition, ClinicalRuleCollectionMatch):
        _validate_condition(condition.where, scope="each_item", depth=depth + 1, errors=errors)
        return
    errors.append(f"Unsupported clinical condition node: {type(condition).__name__}")


def validate_rule_set(document: ClinicalRuleSetDoc) -> ClinicalRuleValidationResult:
    """Validate rule semantics and execute embedded cases when structure permits.

    Args:
        document: Parsed rule set with blocks, declarations, and optional test cases.

    Returns:
        Validity, errors, and warnings. Embedded cases compare ordered matched
        rule IDs and exact section text; evaluation failures become errors.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if document.minimum_engine_version > ENGINE_VERSION:
        errors.append(
            f"Rule set requires engine version {document.minimum_engine_version}; "
            f"this service provides version {ENGINE_VERSION}"
        )
    if not document.blocks:
        errors.append("At least one rule block is required")
    enabled_analyses = {
        block.analysis
        for block in document.blocks
        if block.analysis and any(r.enabled for r in block.rules)
    }
    for analysis in sorted(enabled_analyses):
        declaration = document.analysis_declarations.get(str(analysis))
        if declaration is None or declaration.narrative != "enabled":
            errors.append(f"Analysis '{analysis}' has rules but is not declared as enabled")
    for analysis, declaration in document.analysis_declarations.items():
        if declaration.narrative == "enabled" and analysis not in enabled_analyses:
            warnings.append(f"Analysis '{analysis}' is enabled but has no enabled rule block")

    section_headings: dict[str, bool] = {}
    for block in document.blocks:
        previous = section_headings.setdefault(block.section, block.show_heading)
        if previous != block.show_heading:
            errors.append(f"Section '{block.section}' mixes heading visibility")
        if not block.rules:
            errors.append(f"Block '{block.block_id}' must contain at least one rule")
        for rule in block.rules:
            if rule.condition is not None:
                _validate_condition(
                    rule.condition,
                    scope=block.evaluation.mode,
                    depth=1,
                    errors=errors,
                )
            for node in rule.output:
                path = None
                if isinstance(node, (ClinicalFactOutput, ClinicalListOutput, ClinicalNumberOutput)):
                    path = node.path
                elif isinstance(node, ClinicalMessageOutput):
                    path = node.count_path
                if path:
                    try:
                        validate_fact_path(path, scope=block.evaluation.mode)
                    except ValueError as exc:
                        errors.append(str(exc))
    if not document.test_cases:
        warnings.append("No embedded clinical rule test cases are configured")
    elif not errors:
        from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
        from api.application.reporting.clinical_rules.facts import PreparedReportContext

        candidate = document.model_copy(update={"content_hash": content_hash(document)})
        analyses = {
            analysis
            for analysis, declaration in document.analysis_declarations.items()
            if declaration.narrative == "enabled"
        }
        for test_case in document.test_cases:
            try:
                evaluation = ClinicalRuleEvaluator().evaluate(
                    PreparedReportContext.model_validate(test_case.facts),
                    candidate,
                    reporting_analyses=analyses,
                )
            except (TypeError, ValueError) as exc:
                errors.append(f"Test '{test_case.test_id}' could not be evaluated: {exc}")
                continue
            matched = [entry.rule_id for entry in evaluation.trace if entry.matched]
            if matched != test_case.expected_rule_ids:
                errors.append(
                    f"Test '{test_case.test_id}' matched {matched!r}; "
                    f"expected {test_case.expected_rule_ids!r}"
                )
            if evaluation.sections != test_case.expected_sections:
                errors.append(f"Test '{test_case.test_id}' produced unexpected report text")
    return ClinicalRuleValidationResult(valid=not errors, errors=errors, warnings=warnings)
