"""Configured flag choices and exact SNV filtering across review and reporting."""

import pytest
from coyote.application.query_rules.service import QueryRuleService
from coyote.application.reporting.clinical_rules.evaluator import _predicate_matches
from coyote.application.reporting.clinical_rules.facts import PreparedFindingFacts
from coyote.application.reporting.clinical_rules.preparation import _snv_fact
from coyote.application.reporting.clinical_rules.registry import (
    fact_catalog_payload,
    validate_fact_path,
)
from coyote.config.loaders import filter_flags
from coyote.config.loaders.filter_flags import filter_flag_options
from coyote.contracts.schemas.clinical_rules import ClinicalRulePredicate
from coyote.domain.common.sample_filters import normalize_sample_filters
from pydantic import ValidationError


def test_choices_use_global_and_snv_caller_literals_including_hidden_flags(monkeypatch):
    """Display-only prefixes and flags from other analyses are not literal SNV choices."""
    monkeypatch.setattr(
        filter_flags,
        "load_filter_flag_metadata",
        lambda: {
            "exact": {"PASS": {}},
            "terms": {"HIDDEN": {"hidden": True}},
            "prefixes": {"WARN": {}},
            "callers": {
                "snv": {"example": {"exact": {"CUSTOM": {}}, "terms": {"PASS": {}}}},
                "cnv": {"example": {"exact": {"CNV_ONLY": {}}, "terms": {}}},
            },
        },
    )
    assert filter_flag_options("snv") == ["CUSTOM", "HIDDEN", "PASS"]
    query_fields = QueryRuleService(None).condition_options()["fields"]["snv"]
    assert next(field for field in query_fields if field["path"] == "FILTER")["value_options"] == [
        "CUSTOM",
        "HIDDEN",
        "PASS",
    ]
    clinical_fields = {fact["path"]: fact for fact in fact_catalog_payload()}
    assert clinical_fields["finding.filter_flags"]["value_options"] == ["CUSTOM", "HIDDEN", "PASS"]
    assert clinical_fields["item.filter_flags"]["value_options"] == ["CUSTOM", "HIDDEN", "PASS"]


@pytest.mark.parametrize("intent", ["somatic", "germline"])
def test_flag_filters_remain_intent_scoped_and_deduplicated(intent):
    filters = normalize_sample_filters(
        {intent: {"snv": {"exclude_flags": [" FAIL_NVAF ", "FAIL_NVAF"]}}},
        asp_category="dna",
        intent=intent,
        analysis_intents=[intent],
    )
    assert filters["snv"]["exclude_flags"] == ["FAIL_NVAF"]
    assert (
        normalize_sample_filters(
            {intent: {"snv": {}}},
            asp_category="dna",
            intent=intent,
            analysis_intents=[intent],
        )["snv"]["exclude_flags"]
        == []
    )


@pytest.mark.parametrize(
    "invalid", ["PASS", [None], [{"$ne": None}], [" "], ["x" * 201], ["PASS"] * 101]
)
def test_invalid_flag_selections_are_rejected(invalid):
    with pytest.raises(ValidationError):
        normalize_sample_filters(
            {"somatic": {"snv": {"exclude_flags": invalid}}}, asp_category="dna"
        )


def test_clinical_rule_flags_match_raw_names_and_support_collection_conditions():
    fact = PreparedFindingFacts.model_validate(_snv_fact({"FILTER": ["PASS", "WARN_NOVAR"]}))
    assert fact.filter_flags == ["PASS", "WARN_NOVAR"]
    for path, scope_name in [
        ("finding.filter_flags", "each_finding"),
        ("item.filter_flags", "each_item"),
    ]:
        assert "overlaps" in validate_fact_path(path, scope=scope_name).operators
        predicate = ClinicalRulePredicate(fact=path, operator="contains", value="WARN_NOVAR")
        assert _predicate_matches(predicate, {path.split(".")[0]: fact.model_dump()})[0] is True
        predicate.value = "WARN"
        assert _predicate_matches(predicate, {path.split(".")[0]: fact.model_dump()})[0] is False
    assert _snv_fact({})["filter_flags"] == []
