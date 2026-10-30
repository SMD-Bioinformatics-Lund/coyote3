"""Structural and semantic validation for canonical clinical rule sets."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from coyote3.application.reporting.clinical_rules.registry import (
    BULK_ANNOTATION_FACT_PATHS,
    validate_fact_path,
)
from coyote3.config.clinical_vocabulary import CLINICAL_VOCABULARY
from coyote3.contracts.schemas.clinical_rules import (
    ClinicalCondition,
    ClinicalFactOutput,
    ClinicalListOutput,
    ClinicalMessageOutput,
    ClinicalNumberOutput,
    ClinicalParagraphBreakOutput,
    ClinicalRendererOutput,
    ClinicalRule,
    ClinicalRuleAll,
    ClinicalRuleAny,
    ClinicalRuleCollectionMatch,
    ClinicalRuleNot,
    ClinicalRulePredicate,
    ClinicalRuleSetDoc,
    ClinicalRuleValidationResult,
    ClinicalTextOutput,
)

REPORT_METADATA_SECTIONS = frozenset({"report_header_suffix", "clinical_question"})
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
            "analysis_declarations",
            "terminology",
            "blocks",
            "bulk_annotation_rules",
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


def _validate_annotation_condition(
    condition: ClinicalCondition | None, errors: list[str], depth: int = 0
) -> None:
    """Reject sample measurements and collection conditions in reusable annotation text.

    Args:
        condition: Authored condition; None is an explicit fallback.
        errors: Validation messages populated in place.
        depth: Current nested-condition depth, starting at zero.
    """
    if condition is None:
        return
    if depth > MAX_CONDITION_DEPTH:
        errors.append(f"Condition nesting exceeds {MAX_CONDITION_DEPTH} levels")
        return
    if isinstance(condition, ClinicalRulePredicate):
        if condition.fact not in BULK_ANNOTATION_FACT_PATHS:
            errors.append(f"Bulk annotations cannot use fact '{condition.fact}'")
    elif isinstance(condition, (ClinicalRuleAll, ClinicalRuleAny)):
        for child in condition.children:
            _validate_annotation_condition(child, errors, depth + 1)
    elif isinstance(condition, ClinicalRuleNot):
        _validate_annotation_condition(condition.child, errors, depth + 1)
    else:
        errors.append("Bulk annotations cannot use report collections")


def _first_match_warnings(rules: list[ClinicalRule], label: str) -> list[str]:
    """Identify enabled templates that an earlier unconditional or identical rule shadows.

    Args:
        rules: Ordered alternatives, including disabled rules to ignore.
        label: Section or tier label shown to the rule author.

    Returns:
        Actionable warnings naming alternatives that can never be reached.
    """
    enabled = sorted((rule for rule in rules if rule.enabled), key=lambda rule: rule.order)
    warnings = []
    for index, rule in enumerate(enabled):
        shadow = next(
            (
                earlier
                for earlier in enabled[:index]
                if earlier.condition is None or earlier.condition == rule.condition
            ),
            None,
        )
        if shadow is not None:
            warnings.append(
                f"{label}: rule '{rule.rule_id}' is unreachable because earlier rule "
                f"'{shadow.rule_id}' always matches or has the same condition. "
                "Move the fallback last or refine the conditions."
            )
    return warnings


def validate_rule_set(
    document: ClinicalRuleSetDoc, *, require_tests: bool = False
) -> ClinicalRuleValidationResult:
    """Validate rule semantics, executing embedded cases only on explicit request.

    Args:
        document: Parsed rule set with blocks, declarations, and optional test cases.
        require_tests: Explicitly require and execute embedded cases. False skips them;
            normal authoring, preview and publication use structural validation only.

    Returns:
        Validity, errors, and warnings. Embedded cases compare ordered matched
        rule IDs and exact section text; evaluation failures become errors.
    """
    errors: list[str] = []
    warnings: list[str] = []
    supported = set(CLINICAL_VOCABULARY.analysis_file_keys_by_omics[document.scope.analyte])
    declared = set(document.analysis_declarations) | {
        block.analysis for block in document.blocks if block.analysis
    }
    for analysis in sorted(declared - supported):
        errors.append(f"Analysis '{analysis}' is not supported for {document.scope.analyte}")
    if {"BIOMARKER", "LOH"} & set(document.analysis_declarations) or any(
        block.analysis in {"BIOMARKER", "LOH"} for block in document.blocks
    ):
        errors.append("Declare HRD, MSI, or TMB individually; BIOMARKER and LOH are not supported")
    if not document.blocks and not document.bulk_annotation_rules:
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
    conflict_scopes: dict[str, tuple[str, str | None]] = {}
    for block in document.blocks:
        if block.conflict_group:
            scope = (block.evaluation.mode, block.evaluation.collection)
            previous_scope = conflict_scopes.setdefault(block.conflict_group, scope)
            if scope != previous_scope:
                errors.append(
                    f"Conflict group '{block.conflict_group}' must use the same evaluation "
                    "mode and collection in every block"
                )
            if block.match_strategy not in {"exactly_one", "at_most_one"}:
                errors.append(
                    f"Block '{block.block_id}' in a conflict group must use exactly_one "
                    "or at_most_one"
                )
        enabled_rules = [rule for rule in block.rules if rule.enabled]
        if block.section == "analysis_description" and block.show_heading:
            errors.append("Analysis description uses the report's fixed section heading")
        if block.section in REPORT_METADATA_SECTIONS and any(
            rule.presentation != "paragraph" for rule in block.rules
        ):
            errors.append(f"Section '{block.section}' requires paragraph presentation")
        if block.match_strategy == "first_match":
            warnings.extend(_first_match_warnings(block.rules, f"Block '{block.block_id}'"))
        if (
            block.section in REPORT_METADATA_SECTIONS
            and block.match_strategy == "all_matches"
            and len(enabled_rules) > 1
        ):
            warnings.append(
                f"Block '{block.block_id}' allows overlapping conditions for a single-value "
                "report field. Use exactly_one or at_most_one for alternative values."
            )
        if block.match_strategy in {"exactly_one", "at_most_one"}:
            for index, rule in enumerate(enabled_rules):
                for other in enabled_rules[index + 1 :]:
                    if (
                        rule.condition is None
                        or other.condition is None
                        or rule.condition == other.condition
                    ):
                        warnings.append(
                            f"Block '{block.block_id}' has potentially overlapping rules "
                            f"'{rule.rule_id}' and '{other.rule_id}'; test their shared cases."
                        )
        if block.section in REPORT_METADATA_SECTIONS:
            if block.evaluation.mode != "once" or block.analysis or block.show_heading:
                errors.append(
                    f"Section '{block.section}' must evaluate once for the whole report "
                    "without a section heading"
                )
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
    for tier in (1, 2, 3):
        warnings.extend(
            _first_match_warnings(
                [rule for rule in document.bulk_annotation_rules if rule.tier == tier],
                f"Bulk annotation Tier {tier}",
            )
        )
    for rule in document.bulk_annotation_rules:
        if document.scope.analyte != "dna":
            errors.append("Bulk annotation templates require DNA small variants")
        if (
            rule.enabled
            and all(
                isinstance(node, (ClinicalTextOutput, ClinicalParagraphBreakOutput))
                for node in rule.output
            )
            and not any(
                isinstance(node, ClinicalTextOutput) and node.value.strip() for node in rule.output
            )
        ):
            errors.append(f"Enabled annotation rule '{rule.rule_id}' has empty text")
        _validate_annotation_condition(rule.condition, errors)
        if rule.condition is not None:
            _validate_condition(rule.condition, scope="each_finding", depth=0, errors=errors)
        for node in rule.output:
            if isinstance(node, ClinicalRendererOutput):
                errors.append("Bulk annotations cannot use report sentence renderers")
            path = getattr(node, "path", getattr(node, "count_path", None))
            if path is not None:
                if path not in BULK_ANNOTATION_FACT_PATHS:
                    errors.append(f"Bulk annotations cannot use fact '{path}'")
                else:
                    try:
                        validate_fact_path(path, scope="each_finding")
                    except ValueError as exc:
                        errors.append(str(exc))
    if require_tests and not document.test_cases:
        errors.append("No embedded clinical rule test cases are configured")
    elif require_tests and not errors:
        from coyote3.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
        from coyote3.application.reporting.clinical_rules.facts import PreparedReportContext

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
