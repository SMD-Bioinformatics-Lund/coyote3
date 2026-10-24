"""Configured flag choices and exact SNV filtering across review and reporting."""

from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from pydantic import ValidationError

from api.application.common.release_resources import capture_gene_lists
from api.application.query_rules.service import QueryRuleService
from api.application.reporting.clinical_rules.evaluator import _predicate_matches
from api.application.reporting.clinical_rules.facts import PreparedFindingFacts
from api.application.reporting.clinical_rules.preparation import _snv_fact
from api.application.reporting.clinical_rules.registry import (
    fact_catalog_payload,
    validate_fact_path,
)
from api.application.reporting.dna_report_payload import _build_variant_query
from api.application.sample.catalog import SampleCatalogService
from api.config.loaders import filter_flags
from api.config.loaders.filter_flags import filter_flag_options
from api.contracts.schemas.clinical_rules import ClinicalRulePredicate
from api.domain.common.sample_filters import normalize_sample_filters
from api.domain.core.dna.varqueries import build_query
from api.domain.core.exceptions import AppError
from api.domain.query_conditions import compile_condition
from api.infra.mongo.repositories.samples import SampleRepository
from tests.unit.test_dna_varqueries import _settings


def test_sample_save_persists_exclusions_with_each_intents_other_snv_filters(monkeypatch):
    """The normal filter-save service writes both SNV profiles into one filter snapshot."""
    collection = mongomock.MongoClient().synthetic.samples
    sample = {
        "_id": ObjectId(),
        "version": 1,
        "asp_category": "dna",
        "analysis_intents": ["somatic", "germline"],
    }
    collection.insert_one(sample)
    service = object.__new__(SampleCatalogService)
    service.sample_repository = SampleRepository(
        SimpleNamespace(samples_collection=collection, client=collection.database.client)
    )
    from api.infra.mongo.repositories import samples as repository_module

    audit_events = []
    monkeypatch.setattr(repository_module, "run_transaction", lambda client, work: work(None))
    monkeypatch.setattr(
        repository_module, "enqueue_audit", lambda *args, **kwargs: audit_events.append(kwargs)
    )
    monkeypatch.setattr(repository_module, "invalidate_samples_cache", lambda adapter: None)
    monkeypatch.setattr(service.sample_repository, "invalidate_dashboard_metrics", lambda: None)
    service.gene_list_repository = SimpleNamespace(get_isgl_by_ids=lambda ids: {})
    service._get_formatted_assay_config = lambda sample: {
        "filters": {},
        "gene_list_release": capture_gene_lists([]),
    }
    service.replace_sample_filters(
        sample=sample,
        filters={
            "somatic": {"snv": {"min_depth": 100, "exclude_flags": ["WARN_NOVAR"]}},
            "germline": {"snv": {"min_depth": 30, "exclude_flags": ["FAIL_NVAF"]}},
        },
    )
    saved = collection.find_one({"_id": sample["_id"]})
    assert "exclude_flags" not in saved
    assert "exclude_flags" not in saved["filters"]
    assert saved["filters"]["somatic"]["snv"]["exclude_flags"] == ["WARN_NOVAR"]
    assert saved["filters"]["somatic"]["snv"]["min_depth"] == 100
    assert saved["filters"]["germline"]["snv"]["exclude_flags"] == ["FAIL_NVAF"]
    assert saved["filters"]["germline"]["snv"]["min_depth"] == 30
    assert saved["version"] == 2
    assert audit_events[0]["metadata"]["previous_version"] == 1
    assert audit_events[0]["metadata"]["after"]["filters"] == saved["filters"]
    with pytest.raises(AppError, match="Sample settings changed"):
        service.replace_sample_filters(sample=sample, filters={})
    assert len(audit_events) == 1
    assert collection.find_one({"_id": sample["_id"]})["filters"] == saved["filters"]


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


@pytest.mark.parametrize("intent", ["somatic", "germline"])
def test_flags_restrict_even_admission_exceptions_and_use_exact_membership(intent):
    from api.config.clinical_query_policy import resolved_query_policy

    policy = resolved_query_policy(
        "snv",
        "exception_only",
        [
            {
                "id": "admit",
                "mode": "admit",
                "intents": [intent],
                "condition": {"type": "predicate", "field": "POS", "operator": "gte", "value": 1},
            }
        ],
    )
    collection = mongomock.MongoClient().synthetic.variants
    for index, flags in enumerate((["PASS"], ["PASS", "FAIL_NVAF"], ["PASS_EXTRA"], [], None)):
        row = {"SAMPLE_ID": "SAMPLE_1", "POS": index + 1}
        if flags is not None:
            row["FILTER"] = flags
        collection.insert_one(row)
    settings = _settings(exclude_flags=["FAIL_NVAF"])
    query = build_query("demo", settings, intent=intent, policy=policy)
    assert [row["POS"] for row in collection.find(query)] == [1, 3, 4, 5]
    settings["exclude_flags"] = ["PASS"]
    assert [
        row["POS"]
        for row in collection.find(build_query("demo", settings, intent=intent, policy=policy))
    ] == [3, 4, 5]
    settings["exclude_flags"] = []
    assert (
        collection.count_documents(build_query("demo", settings, intent=intent, policy=policy)) == 5
    )


def test_query_conditions_resolve_active_flag_filters():
    node = {
        "type": "predicate",
        "field": "FILTER",
        "operator": "nin",
        "value": {"source": "sample.filters", "key": "exclude_flags"},
    }
    assert compile_condition(node, "snv", filter_values={"exclude_flags": ["PASS"]}) == {
        "FILTER": {"$nin": ["PASS"]}
    }
    with pytest.raises(ValueError, match="context"):
        compile_condition(node, "snv")
    with pytest.raises(ValueError, match="Unknown cnv field"):
        compile_condition(node, "cnv", filter_values={"exclude_flags": ["PASS"]})


@pytest.mark.parametrize("intent", ["somatic", "germline"])
def test_report_query_preserves_flag_filters(intent):
    query = _build_variant_query(
        "demo",
        {"_id": "SAMPLE_1"},
        {intent: {"snv": {"exclude_flags": ["WARN_NOVAR"]}}},
        [],
        [],
        [],
        False,
        intent=intent,
    )
    assert {"FILTER": {"$nin": ["WARN_NOVAR"]}} in query["$and"]


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
