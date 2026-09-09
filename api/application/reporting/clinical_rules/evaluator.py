"""Deterministic evaluator for canonical clinical reporting rule sets."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from api.application.reporting.clinical_rules.facts import PreparedReportContext
from api.application.reporting.clinical_rules.renderers import render_named
from api.contracts.schemas.clinical_rules import (
    ClinicalCondition,
    ClinicalConditionTraceNode,
    ClinicalFactOutput,
    ClinicalListOutput,
    ClinicalMessageOutput,
    ClinicalNumberOutput,
    ClinicalOutputNode,
    ClinicalParagraphBreakOutput,
    ClinicalRendererOutput,
    ClinicalRule,
    ClinicalRuleAll,
    ClinicalRuleAny,
    ClinicalRuleCollectionMatch,
    ClinicalRuleEvaluation,
    ClinicalRuleNot,
    ClinicalRuleOperator,
    ClinicalRulePredicate,
    ClinicalRuleSetDoc,
    ClinicalRuleSourceRef,
    ClinicalRuleTraceEntry,
    ClinicalTextOutput,
)


def resolve_path(scope: Mapping[str, Any], path: str) -> tuple[Any, bool]:
    """Walk a dotted path through mappings, distinguishing absent keys from nulls.

    Args:
        scope: Fact mappings to traverse.
        path: Dot-separated keys; list indexing is not supported.

    Returns:
        The stored value and True, or (None, False) when traversal fails.
    """
    value: Any = scope
    for part in path.split("."):
        if isinstance(value, Mapping) and part in value:
            value = value[part]
        else:
            return None, False
    return value, True


def _compare(operator: str, actual: Any, expected: Any) -> bool:
    """Apply a scalar equality or ordering operator.

    Args:
        operator: One of eq, ne, gt, gte, lt, or lte.
        actual: Left-hand operand from the prepared facts.
        expected: Right-hand operand from the rule.

    Returns:
        Whether the comparison holds.

    Raises:
        ValueError: The operator is unsupported.
        TypeError: The operands cannot be ordered for the selected operator.
    """
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "gt":
        return actual > expected
    if operator == "gte":
        return actual >= expected
    if operator == "lt":
        return actual < expected
    if operator == "lte":
        return actual <= expected
    raise ValueError(f"Unsupported comparison operator '{operator}'")


def _predicate_matches(
    predicate: ClinicalRulePredicate, scope: Mapping[str, Any]
) -> tuple[bool, list[str]]:
    """Evaluate a predicate and identify an absent fact path.

    Args:
        predicate: Fact path, operator, and comparison value.
        scope: Prepared facts visible to the rule.

    Returns:
        Match status and missing paths. Comparisons raising TypeError do not
        match; other comparisons retain their operator semantics. Existence
        checks do not report absent paths as missing facts.
    """
    actual, exists = resolve_path(scope, predicate.fact)
    operator = predicate.operator
    if operator == ClinicalRuleOperator.EXISTS:
        return exists is bool(predicate.value), []
    if not exists:
        return False, [predicate.fact]
    if operator == ClinicalRuleOperator.IS_UNKNOWN:
        return actual is None or actual == "unknown", []
    if operator == ClinicalRuleOperator.IS_EMPTY:
        return actual in ("", [], (), {}, set()), []
    try:
        if operator == ClinicalRuleOperator.EQ:
            return actual == predicate.value, []
        if operator == ClinicalRuleOperator.NE:
            return actual != predicate.value, []
        if operator == ClinicalRuleOperator.IN:
            return actual in predicate.value, []
        if operator == ClinicalRuleOperator.NOT_IN:
            return actual not in predicate.value, []
        if operator == ClinicalRuleOperator.CONTAINS:
            return (
                isinstance(actual, (Sequence, set, frozenset)) and predicate.value in actual,
                [],
            )
        if operator == ClinicalRuleOperator.OVERLAPS:
            if isinstance(actual, str) or not isinstance(actual, (Sequence, set, frozenset)):
                return False, []
            return bool(set(actual) & set(predicate.value)), []
        if operator == ClinicalRuleOperator.BETWEEN:
            lower, upper = predicate.value
            return lower <= actual <= upper, []
        return _compare(operator.value, actual, predicate.value), []
    except TypeError:
        return False, []


def condition_matches(
    condition: ClinicalCondition | None,
    scope: Mapping[str, Any],
) -> tuple[bool, list[str]]:
    """Evaluate a condition tree, retaining paths missing from its fact scope.

    Args:
        condition: Predicate or compound condition; None always matches.
        scope: Prepared facts, with collection elements exposed as item.

    Returns:
        Match status and reported missing paths. Reported missing paths prevent
        negation and collection matches. Existence predicates report no missing
        paths, so negating an existence check can match an absent fact.
        An all-quantified empty collection does not match.

    Raises:
        ValueError: A condition node or count comparison operator is unsupported.
    """
    if condition is None:
        return True, []
    if isinstance(condition, ClinicalRulePredicate):
        return _predicate_matches(condition, scope)
    if isinstance(condition, ClinicalRuleNot):
        matched, missing = condition_matches(condition.child, scope)
        if missing:
            return False, missing
        return not matched, missing
    if isinstance(condition, (ClinicalRuleAll, ClinicalRuleAny)):
        results = [condition_matches(child, scope) for child in condition.children]
        missing = sorted({path for _matched, paths in results for path in paths})
        matches = [matched for matched, _paths in results]
        return (all(matches) if isinstance(condition, ClinicalRuleAll) else any(matches)), missing
    if isinstance(condition, ClinicalRuleCollectionMatch):
        values, exists = resolve_path(scope, condition.collection)
        if not exists:
            return False, [condition.collection]
        if not isinstance(values, list):
            return False, []
        results = [condition_matches(condition.where, {**scope, "item": item}) for item in values]
        missing = sorted({path for _matched, paths in results for path in paths})
        if missing:
            return False, missing
        matches = [matched for matched, _paths in results]
        if condition.quantifier == "any":
            return any(matches), missing
        if condition.quantifier == "none":
            return not any(matches), missing
        if condition.quantifier == "all":
            return bool(values) and all(matches), missing
        assert condition.count is not None
        return _compare(condition.count.operator, sum(matches), condition.count.value), missing
    raise ValueError(f"Unsupported clinical condition node: {type(condition).__name__}")


def condition_matches_with_trace(
    condition: ClinicalCondition | None,
    scope: Mapping[str, Any],
) -> tuple[bool, list[str], ClinicalConditionTraceNode]:
    """Evaluate a condition and retain its nested decision tree for testing previews."""
    if condition is None:
        return True, [], ClinicalConditionTraceNode(type="always", label="Always", matched=True)
    if isinstance(condition, ClinicalRulePredicate):
        matched, missing = _predicate_matches(condition, scope)
        expected = (
            ""
            if condition.operator
            in {ClinicalRuleOperator.IS_EMPTY, ClinicalRuleOperator.IS_UNKNOWN}
            else f" {condition.value!r}"
        )
        return (
            matched,
            missing,
            ClinicalConditionTraceNode(
                type="predicate",
                label=f"{condition.fact} {condition.operator.value}{expected}",
                matched=matched,
                missing_facts=missing,
            ),
        )
    if isinstance(condition, ClinicalRuleNot):
        child_matched, missing, child_trace = condition_matches_with_trace(condition.child, scope)
        matched = False if missing else not child_matched
        return (
            matched,
            missing,
            ClinicalConditionTraceNode(
                type="not",
                label="Exclude when",
                matched=matched,
                missing_facts=missing,
                children=[child_trace],
            ),
        )
    if isinstance(condition, (ClinicalRuleAll, ClinicalRuleAny)):
        results = [condition_matches_with_trace(child, scope) for child in condition.children]
        missing = sorted({path for _matched, paths, _trace in results for path in paths})
        matches = [matched for matched, _paths, _trace in results]
        matched = all(matches) if isinstance(condition, ClinicalRuleAll) else any(matches)
        return (
            matched,
            missing,
            ClinicalConditionTraceNode(
                type=condition.type,
                label="Match all" if isinstance(condition, ClinicalRuleAll) else "Match any",
                matched=matched,
                missing_facts=missing,
                children=[trace for _matched, _missing, trace in results],
            ),
        )
    if isinstance(condition, ClinicalRuleCollectionMatch):
        values, exists = resolve_path(scope, condition.collection)
        label = f"{condition.quantifier} in {condition.collection}"
        if not exists:
            missing = [condition.collection]
            return (
                False,
                missing,
                ClinicalConditionTraceNode(
                    type="collection_match",
                    label=label,
                    matched=False,
                    missing_facts=missing,
                ),
            )
        if not isinstance(values, list):
            return (
                False,
                [],
                ClinicalConditionTraceNode(type="collection_match", label=label, matched=False),
            )
        results = [
            condition_matches_with_trace(condition.where, {**scope, "item": item})
            for item in values
        ]
        missing = sorted({path for _matched, paths, _trace in results for path in paths})
        matches = [matched for matched, _paths, _trace in results]
        if missing:
            matched = False
        elif condition.quantifier == "any":
            matched = any(matches)
        elif condition.quantifier == "none":
            matched = not any(matches)
        elif condition.quantifier == "all":
            matched = bool(values) and all(matches)
        else:
            assert condition.count is not None
            matched = _compare(condition.count.operator, sum(matches), condition.count.value)
        children = [
            trace.model_copy(update={"label": f"Item {index}: {trace.label}"})
            for index, (_matched, _missing, trace) in enumerate(results, start=1)
        ]
        return (
            matched,
            missing,
            ClinicalConditionTraceNode(
                type="collection_match",
                label=label,
                matched=matched,
                missing_facts=missing,
                children=children,
            ),
        )
    raise ValueError(f"Unsupported clinical condition node: {type(condition).__name__}")


def _format_value(value: Any, formatter: str) -> str:
    """Convert a fact to text and apply the requested case conversion.

    Args:
        value: Fact value to stringify.
        formatter: gene_symbol or upper uppercases; lower lowercases;
            other values preserve case.

    Returns:
        Formatted text.
    """
    text = str(value)
    if formatter in {"gene_symbol", "upper"}:
        return text.upper()
    if formatter == "lower":
        return text.lower()
    return text


def _render_output_node(
    node: ClinicalOutputNode,
    *,
    scope: dict[str, Any],
    terminology: dict[str, Any],
) -> str:
    """Render one typed output node using facts and named terminology.

    Args:
        node: Literal, fact, list, number, message, or named-renderer output.
        scope: Facts available for dotted-path lookup.
        terminology: Wording configuration passed to named renderers.

    Returns:
        Rendered text, or an empty string for an omitted missing fact.

    Raises:
        ValueError: The node is unsupported, a required fact is absent or null,
            a list or number has the wrong type, or a named renderer fails.
    """
    if isinstance(node, ClinicalTextOutput):
        return node.value
    if isinstance(node, ClinicalParagraphBreakOutput):
        return "\n\n"
    if isinstance(node, ClinicalRendererOutput):
        defaults = {
            "tier_summary": "aggregates.tier_summaries",
            "fusion_summary": "findings",
        }
        source_path = node.source or defaults.get(node.name)
        source = resolve_path(scope, source_path)[0] if source_path else None
        return render_named(node.name, source=source, scope=scope, terminology=terminology)
    if isinstance(node, (ClinicalFactOutput, ClinicalListOutput, ClinicalNumberOutput)):
        path = node.path
    elif isinstance(node, ClinicalMessageOutput):
        path = node.count_path
    else:
        raise ValueError(f"Unsupported clinical output node: {type(node).__name__}")
    value, exists = resolve_path(scope, path)
    missing_policy = getattr(node, "missing", "error")
    if not exists or value is None:
        if missing_policy == "omit":
            return ""
        raise ValueError(f"Clinical output fact '{path}' is missing")
    if isinstance(node, ClinicalFactOutput):
        return _format_value(value, node.formatter)
    if isinstance(node, ClinicalListOutput):
        if not isinstance(value, list):
            raise ValueError(f"Clinical output fact '{path}' is not a list")
        values = [_format_value(item, node.formatter) for item in value]
        if len(values) < 2:
            return "".join(values)
        return ", ".join(values[:-1]) + f" {node.conjunction} " + values[-1]
    if isinstance(node, ClinicalNumberOutput):
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"Clinical output fact '{path}' is not numeric")
        return f"{value:.{node.precision}f}{node.unit}"
    return node.one if value == 1 else node.other


def render_rule(rule: ClinicalRule, *, scope: dict[str, Any], terminology: dict[str, Any]) -> str:
    """Concatenate a rule's output nodes in their configured order.

    Args:
        rule: Rule whose output is rendered without checking its condition.
        scope: Prepared facts available to output nodes.
        terminology: Wording configuration for named renderers.

    Returns:
        Combined text without an added separator.

    Raises:
        ValueError: An output node cannot be rendered from the supplied facts.
    """
    return "".join(
        _render_output_node(node, scope=scope, terminology=terminology) for node in rule.output
    )


def _collection_items(context: PreparedReportContext, collection: str) -> list[dict[str, Any]]:
    """Extract mapping elements from a prepared-context collection.

    Args:
        context: Facts from which to build the evaluation scope.
        collection: Dotted path to a list.

    Returns:
        Shallow dictionary copies of mapping elements, or an empty list for
        an absent or non-list collection.
    """
    scope = context.evaluation_scope()
    values, exists = resolve_path(scope, collection)
    if not exists or not isinstance(values, list):
        return []
    return [dict(value) for value in values if isinstance(value, Mapping)]


class ClinicalRuleEvaluator:
    """Evaluate one immutable canonical rule document against prepared facts."""

    def evaluate(
        self,
        context: PreparedReportContext,
        rule_set: ClinicalRuleSetDoc,
        *,
        reporting_analyses: set[str],
        include_condition_trace: bool = False,
    ) -> ClinicalRuleEvaluation:
        """Render enabled rules and record decisions in section and rule order.

        Args:
            context: Prepared report facts; this method does not filter findings.
            rule_set: Canonical rule document and provenance to evaluate.
            reporting_analyses: Analyses whose named blocks may run; blocks
                without an analysis are also evaluated.
            include_condition_trace: Include nested condition decisions when True.

        Returns:
            Source provenance, section text, heading visibility, and rule traces.

        Raises:
            ValueError: Rendering fails, a block violates its match cardinality,
                or rendered blocks disagree on section heading visibility.

        Notes:
            first_match stops after the first nonblank matched output for each
            candidate. Disabled rules and excluded analyses have no trace entries.
        """
        sections: dict[str, list[str]] = {}
        section_headings: dict[str, bool] = {}
        trace: list[ClinicalRuleTraceEntry] = []
        blocks = sorted(rule_set.blocks, key=lambda block: (block.section_order, block.block_order))
        for block in blocks:
            if block.analysis and block.analysis not in reporting_analyses:
                continue
            if block.evaluation.mode == "each_finding":
                candidates = [
                    (finding, None, str(index)) for index, finding in enumerate(context.findings)
                ]
            elif block.evaluation.mode == "each_item":
                candidates = [
                    (None, item, str(index))
                    for index, item in enumerate(
                        _collection_items(context, str(block.evaluation.collection))
                    )
                ]
            else:
                candidates = [(None, None, None)]

            for finding, item, item_identity in candidates:
                scope = context.evaluation_scope(finding=finding, item=item)
                matches: list[tuple[ClinicalRule, str]] = []
                candidate_trace: list[ClinicalRuleTraceEntry] = []
                for rule in sorted(block.rules, key=lambda candidate: candidate.order):
                    if not rule.enabled:
                        continue
                    if include_condition_trace:
                        matched, missing, condition_trace = condition_matches_with_trace(
                            rule.condition, scope
                        )
                    else:
                        matched, missing = condition_matches(rule.condition, scope)
                        condition_trace = None
                    rendered = (
                        render_rule(rule, scope=scope, terminology=rule_set.terminology)
                        if matched
                        else None
                    )
                    candidate_trace.append(
                        ClinicalRuleTraceEntry(
                            block_id=block.block_id,
                            rule_id=rule.rule_id,
                            section=block.section,
                            matched=matched,
                            item_identity=item_identity,
                            missing_facts=missing,
                            rendered_text=rendered,
                            condition_trace=condition_trace,
                        )
                    )
                    if matched and rendered and rendered.strip():
                        matches.append((rule, rendered))
                        if block.match_strategy == "first_match":
                            break
                trace.extend(candidate_trace)
                if block.match_strategy == "exactly_one" and len(matches) != 1:
                    raise ValueError(
                        f"Clinical rule block '{block.block_id}' required exactly one match; "
                        f"found {len(matches)}"
                    )
                if block.match_strategy == "at_most_one" and len(matches) > 1:
                    raise ValueError(
                        f"Clinical rule block '{block.block_id}' permits at most one match; "
                        f"found {len(matches)}"
                    )
                for _rule, text in matches:
                    existing = section_headings.get(block.section)
                    if existing is not None and existing != block.show_heading:
                        raise ValueError(
                            f"Clinical rule section '{block.section}' mixes heading modes"
                        )
                    section_headings[block.section] = block.show_heading
                    sections.setdefault(block.section, []).append(text)

        return ClinicalRuleEvaluation(
            source=ClinicalRuleSourceRef(
                rule_set_oid=str(rule_set.id_),
                rule_set_id=rule_set.rule_set_id,
                schema_version=rule_set.schema_version,
                content_version=rule_set.content_version,
                content_hash=str(rule_set.content_hash or ""),
                language=rule_set.scope.language,
                effective_from=rule_set.effective_from,
            ),
            sections=sections,
            section_headings=section_headings,
            trace=trace,
        )
