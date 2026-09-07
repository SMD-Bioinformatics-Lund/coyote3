"""Branch-complete tests for deterministic clinical-rule evaluation."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

import pytest
from bson import ObjectId

from api.application.reporting.clinical_rules.evaluator import (
    _collection_items,
    _compare,
    _format_value,
    _render_output_node,
    condition_matches,
    condition_matches_with_trace,
    render_rule,
    resolve_path,
)
from api.application.reporting.clinical_rules.facts import PreparedReportContext
from api.application.reporting.clinical_rules.validation import content_hash
from api.contracts.schemas.clinical_rules import (
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
    ClinicalTextOutput,
)


def _context() -> PreparedReportContext:
    return PreparedReportContext.model_validate(
        {
            "sample": {
                "name": "SYNTHETIC",
                "asp_id": "assay_1",
                "subpanel_id": "base",
                "environment": "testing",
                "omics_layer": "dna",
                "paired": False,
            },
            "asp": {"asp_id": "assay_1", "accredited": True},
            "aspc": {
                "aspc_id": "assay_1_base_testing",
                "asp_id": "assay_1",
                "subpanel_id": "base",
                "environment": "testing",
                "reporting": {
                    "report_sections": ["SNV"],
                    "clinical_rule_set_id": "assay_1__base__sv",
                },
            },
            "findings": [
                {"kind": "snv", "gene": "TP53", "genes": ["TP53"], "tier": 1},
                {"kind": "snv", "gene": "KRAS", "genes": ["KRAS"], "tier": 2},
            ],
            "aggregates": {"finding_count": 2, "snv_count": 2},
        }
    )


def _rule(rule_id: str, text: str, *, condition=None, enabled: bool = True) -> dict:
    return {
        "rule_id": rule_id,
        "name": rule_id,
        "order": 10,
        "enabled": enabled,
        "condition": condition,
        "output": [{"type": "text", "value": text}],
    }


def _document(blocks: list[dict]) -> ClinicalRuleSetDoc:
    now = datetime.now(timezone.utc)
    document = ClinicalRuleSetDoc.model_validate(
        {
            "_id": ObjectId(),
            "rule_set_id": "assay_1__base__sv",
            "content_version": 1,
            "revision": 1,
            "scope": {
                "asp_id": "assay_1",
                "subpanel_id": "base",
                "analyte": "dna",
                "language": "sv",
            },
            "name": "Rules",
            "status": "published",
            "active": True,
            "analysis_declarations": {"SNV": {"narrative": "enabled"}},
            "blocks": blocks,
            "created_at": now,
            "created_by": "author",
            "updated_at": now,
            "updated_by": "author",
            "published_at": now,
            "published_by": "publisher",
            "effective_from": now,
        }
    )
    document.content_hash = content_hash(document)
    return document


def _block(
    *,
    strategy: str = "all_matches",
    mode: str = "once",
    rules: list[dict] | None = None,
    analysis: str | None = "SNV",
    section: str = "Summary",
    heading: bool = True,
) -> dict:
    evaluation = {"mode": mode}
    if mode == "each_item":
        evaluation["collection"] = "findings"
    return {
        "block_id": f"{section}_{mode}_{strategy}",
        "name": section,
        "analysis": analysis,
        "evaluation": evaluation,
        "section": section,
        "section_order": 100,
        "block_order": 10,
        "show_heading": heading,
        "match_strategy": strategy,
        "rules": rules or [_rule("always", "Text")],
    }


def test_path_resolution_and_scalar_comparisons() -> None:
    assert resolve_path({"a": {"b": 2}}, "a.b") == (2, True)
    assert resolve_path({"a": []}, "a.b") == (None, False)
    assert _compare("eq", 1, 1)
    assert _compare("ne", 1, 2)
    assert _compare("gt", 2, 1)
    assert _compare("gte", 2, 2)
    assert _compare("lt", 1, 2)
    assert _compare("lte", 2, 2)
    with pytest.raises(ValueError, match="Unsupported comparison"):
        _compare("between", 1, 2)


@pytest.mark.parametrize(
    ("operator", "actual", "expected", "matched"),
    [
        ("eq", "A", "A", True),
        ("ne", "A", "B", True),
        ("in", "A", ["A", "B"], True),
        ("not_in", "A", ["B"], True),
        ("contains", ["A", "B"], "A", True),
        ("contains", 3, 3, False),
        ("overlaps", ["A", "B"], ["B"], True),
        ("overlaps", "AB", ["A"], False),
        ("overlaps", 3, [3], False),
        ("between", 2, [1, 3], True),
        ("gt", "not-a-number", 2, False),
    ],
)
def test_predicate_operator_matrix(operator, actual, expected, matched) -> None:
    predicate = ClinicalRulePredicate(fact="value", operator=operator, value=expected)
    assert condition_matches(predicate, {"value": actual}) == (matched, [])


def test_predicate_missing_existence_unknown_and_empty_semantics() -> None:
    assert condition_matches(
        ClinicalRulePredicate(fact="missing", operator="exists", value=False), {}
    ) == (True, [])
    assert condition_matches(
        ClinicalRulePredicate(fact="present", operator="exists", value=True), {"present": None}
    ) == (True, [])
    assert condition_matches(ClinicalRulePredicate(fact="missing", operator="eq", value=0), {}) == (
        False,
        ["missing"],
    )
    for value in (None, "unknown"):
        assert condition_matches(
            ClinicalRulePredicate(fact="value", operator="is_unknown"), {"value": value}
        ) == (True, [])
    for value in ("", [], (), {}, set()):
        assert condition_matches(
            ClinicalRulePredicate(fact="value", operator="is_empty"), {"value": value}
        ) == (True, [])


def test_nested_boolean_and_collection_conditions() -> None:
    yes = ClinicalRulePredicate(fact="value", operator="eq", value=1)
    missing = ClinicalRulePredicate(fact="missing", operator="eq", value=1)
    assert condition_matches(None, {}) == (True, [])
    assert condition_matches(ClinicalRuleNot(child=yes), {"value": 2}) == (True, [])
    assert condition_matches(ClinicalRuleNot(child=missing), {}) == (False, ["missing"])
    assert condition_matches(ClinicalRuleAll(children=[yes, missing]), {"value": 1}) == (
        False,
        ["missing"],
    )
    assert condition_matches(ClinicalRuleAny(children=[yes, missing]), {"value": 1}) == (
        True,
        ["missing"],
    )

    where = ClinicalRulePredicate(fact="item.tier", operator="gte", value=2)
    for quantifier, expected in (("any", True), ("none", False), ("all", False)):
        condition = ClinicalRuleCollectionMatch(
            collection="findings", quantifier=quantifier, where=where
        )
        assert condition_matches(condition, {"findings": [{"tier": 1}, {"tier": 2}]})[0] is expected
    empty_all = ClinicalRuleCollectionMatch(collection="findings", quantifier="all", where=where)
    assert condition_matches(empty_all, {"findings": []}) == (False, [])
    count = ClinicalRuleCollectionMatch(
        collection="findings",
        quantifier="count",
        where=where,
        count={"operator": "eq", "value": 1},
    )
    assert condition_matches(count, {"findings": [{"tier": 2}]}) == (True, [])
    assert condition_matches(count, {}) == (False, ["findings"])
    assert condition_matches(count, {"findings": "wrong"}) == (False, [])
    missing_item = ClinicalRuleCollectionMatch(
        collection="findings", quantifier="any", where=missing
    )
    assert condition_matches(missing_item, {"findings": [{}]}) == (False, ["missing"])
    with pytest.raises(ValueError, match="Unsupported clinical condition"):
        condition_matches(object(), {})  # type: ignore[arg-type]


def test_condition_execution_trace_covers_nested_and_collection_decisions() -> None:
    matched, missing, trace = condition_matches_with_trace(None, {})
    assert (matched, missing, trace.label) == (True, [], "Always")

    predicate = ClinicalRulePredicate(fact="value", operator="eq", value=1)
    matched, missing, trace = condition_matches_with_trace(predicate, {"value": 1})
    assert (matched, missing, trace.matched) == (True, [], True)
    assert trace.label == "value eq 1"
    _, _, empty_trace = condition_matches_with_trace(
        ClinicalRulePredicate(fact="value", operator="is_empty"), {"value": ""}
    )
    assert empty_trace.label == "value is_empty"

    nested = ClinicalRuleAll(
        children=[
            predicate,
            ClinicalRuleNot(child=ClinicalRulePredicate(fact="other", operator="eq", value=2)),
        ]
    )
    matched, missing, trace = condition_matches_with_trace(nested, {"value": 1, "other": 3})
    assert (matched, missing, len(trace.children)) == (True, [], 2)
    missing_not = ClinicalRuleNot(
        child=ClinicalRulePredicate(fact="missing", operator="eq", value=1)
    )
    assert condition_matches_with_trace(missing_not, {})[:2] == (False, ["missing"])
    any_condition = ClinicalRuleAny(children=[predicate, missing_not.child])
    assert condition_matches_with_trace(any_condition, {"value": 1})[:2] == (
        True,
        ["missing"],
    )

    where = ClinicalRulePredicate(fact="item.tier", operator="gte", value=2)
    for quantifier, expected in (("any", True), ("none", False), ("all", False)):
        collection = ClinicalRuleCollectionMatch(
            collection="findings", quantifier=quantifier, where=where
        )
        matched, missing, trace = condition_matches_with_trace(
            collection, {"findings": [{"tier": 1}, {"tier": 2}]}
        )
        assert (matched, missing, len(trace.children)) == (expected, [], 2)
        assert trace.children[0].label.startswith("Item 1:")
    count = ClinicalRuleCollectionMatch(
        collection="findings",
        quantifier="count",
        where=where,
        count={"operator": "eq", "value": 1},
    )
    assert condition_matches_with_trace(count, {"findings": [{"tier": 2}]})[0] is True
    assert condition_matches_with_trace(count, {})[:2] == (False, ["findings"])
    assert condition_matches_with_trace(count, {"findings": "invalid"})[:2] == (False, [])
    missing_items = ClinicalRuleCollectionMatch(
        collection="findings",
        quantifier="any",
        where=ClinicalRulePredicate(fact="item.tier", operator="eq", value=1),
    )
    assert condition_matches_with_trace(missing_items, {"findings": [{}]})[:2] == (
        False,
        ["item.tier"],
    )
    with pytest.raises(ValueError, match="Unsupported clinical condition"):
        condition_matches_with_trace(object(), {})  # type: ignore[arg-type]


def test_output_node_matrix_and_failures() -> None:
    scope = {
        "gene": "tp53",
        "words": ["one", "two", "three"],
        "one_word": ["only"],
        "empty": [],
        "number": 1.234,
        "count": 1,
        "boolean": True,
    }
    terms = {"tier_summary": {}}
    assert _format_value("tp53", "gene_symbol") == "TP53"
    assert _format_value("Text", "upper") == "TEXT"
    assert _format_value("Text", "lower") == "text"
    assert _format_value("Text", "text") == "Text"
    assert (
        _render_output_node(ClinicalTextOutput(value="text"), scope=scope, terminology=terms)
        == "text"
    )
    assert (
        _render_output_node(ClinicalParagraphBreakOutput(), scope=scope, terminology=terms)
        == "\n\n"
    )
    assert (
        _render_output_node(
            ClinicalFactOutput(path="gene", formatter="upper"), scope=scope, terminology=terms
        )
        == "TP53"
    )
    assert (
        _render_output_node(
            ClinicalListOutput(path="words", conjunction="and"), scope=scope, terminology=terms
        )
        == "one, two and three"
    )
    assert (
        _render_output_node(ClinicalListOutput(path="one_word"), scope=scope, terminology=terms)
        == "only"
    )
    assert (
        _render_output_node(ClinicalListOutput(path="empty"), scope=scope, terminology=terms) == ""
    )
    assert (
        _render_output_node(
            ClinicalNumberOutput(path="number", precision=2, unit="%"),
            scope=scope,
            terminology=terms,
        )
        == "1.23%"
    )
    assert (
        _render_output_node(
            ClinicalMessageOutput(count_path="count", one="one", other="many"),
            scope=scope,
            terminology=terms,
        )
        == "one"
    )
    assert (
        _render_output_node(
            ClinicalMessageOutput(count_path="number", one="one", other="many"),
            scope=scope,
            terminology=terms,
        )
        == "many"
    )
    assert (
        _render_output_node(
            ClinicalFactOutput(path="missing", missing="omit"), scope=scope, terminology=terms
        )
        == ""
    )
    with pytest.raises(ValueError, match="is missing"):
        _render_output_node(ClinicalFactOutput(path="missing"), scope=scope, terminology=terms)
    with pytest.raises(ValueError, match="is not a list"):
        _render_output_node(ClinicalListOutput(path="gene"), scope=scope, terminology=terms)
    with pytest.raises(ValueError, match="is not numeric"):
        _render_output_node(ClinicalNumberOutput(path="boolean"), scope=scope, terminology=terms)
    with pytest.raises(ValueError, match="Unsupported clinical output"):
        _render_output_node(object(), scope=scope, terminology=terms)  # type: ignore[arg-type]


def test_renderer_output_source_defaults_and_explicit_source(monkeypatch) -> None:
    observed = []

    def fake(name, *, source, scope, terminology):
        observed.append((name, source, scope, terminology))
        return name

    monkeypatch.setattr("api.application.reporting.clinical_rules.evaluator.render_named", fake)
    scope = {"findings": [1], "aggregates": {"tier_summaries": [2]}, "custom": [3]}
    for node in (
        ClinicalRendererOutput(name="fusion_summary"),
        ClinicalRendererOutput(name="tier_summary"),
        ClinicalRendererOutput(name="dna_report_intro"),
        ClinicalRendererOutput(name="fusion_summary", source="custom"),
    ):
        _render_output_node(node, scope=scope, terminology={})
    assert [item[1] for item in observed] == [[1], [2], None, [3]]


def test_render_rule_and_collection_item_filtering() -> None:
    rule = ClinicalRule(
        rule_id="r",
        name="R",
        order=1,
        output=[ClinicalTextOutput(value="A"), ClinicalTextOutput(value="B")],
    )
    assert render_rule(rule, scope={}, terminology={}) == "AB"
    context = _context()
    assert len(_collection_items(context, "findings")) == 2
    assert _collection_items(context, "missing") == []
    broken = deepcopy(context.model_dump(mode="python"))
    broken["findings"] = []
    assert _collection_items(PreparedReportContext.model_validate(broken), "findings") == []


def test_evaluator_modes_strategies_disabled_rules_and_analysis_gates() -> None:
    from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator

    blocks = [
        _block(analysis="CNV", section="Skipped"),
        _block(
            mode="each_finding",
            strategy="first_match",
            section="Findings",
            rules=[
                _rule("disabled", "No", enabled=False),
                {**_rule("first", "First"), "order": 20},
                {**_rule("later", "Later"), "order": 30},
            ],
        ),
        _block(mode="each_item", section="Items", rules=[_rule("item", "Item")]),
        _block(strategy="exactly_one", section="Exact", rules=[_rule("exact", "Exact")]),
        _block(strategy="at_most_one", section="Optional", rules=[_rule("blank", "   ")]),
    ]
    result = ClinicalRuleEvaluator().evaluate(
        _context(),
        _document(blocks),
        reporting_analyses={"SNV"},
        include_condition_trace=True,
    )
    assert result.sections == {
        "Findings": ["First", "First"],
        "Items": ["Item", "Item"],
        "Exact": ["Exact"],
    }
    assert "Skipped" not in result.sections
    assert all(entry.rule_id != "disabled" for entry in result.trace)
    assert all(entry.condition_trace is not None for entry in result.trace)


@pytest.mark.parametrize(
    ("strategy", "rules", "message"),
    [
        (
            "exactly_one",
            [
                _rule(
                    "no",
                    "No",
                    condition={
                        "type": "predicate",
                        "fact": "sample.paired",
                        "operator": "eq",
                        "value": True,
                    },
                )
            ],
            "required exactly one",
        ),
        (
            "exactly_one",
            [_rule("a", "A"), {**_rule("b", "B"), "order": 20}],
            "required exactly one",
        ),
        ("at_most_one", [_rule("a", "A"), {**_rule("b", "B"), "order": 20}], "permits at most one"),
    ],
)
def test_evaluator_rejects_invalid_match_cardinality(strategy, rules, message) -> None:
    from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator

    with pytest.raises(ValueError, match=message):
        ClinicalRuleEvaluator().evaluate(
            _context(),
            _document([_block(strategy=strategy, rules=rules)]),
            reporting_analyses={"SNV"},
        )


def test_evaluator_rejects_mixed_heading_modes_at_runtime() -> None:
    from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator

    first = _block(section="First", heading=True, rules=[_rule("first", "First")])
    second = _block(section="Second", heading=False, rules=[_rule("second", "Second")])
    second["block_id"] = "second"
    second["section_order"] = 200
    document = _document([first, second])
    document.blocks[1].section = "First"
    with pytest.raises(ValueError, match="mixes heading modes"):
        ClinicalRuleEvaluator().evaluate(_context(), document, reporting_analyses={"SNV"})
