"""Configured flag choices and exact SNV filtering across review and reporting."""

from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from coyote.application.common.release_resources import capture_gene_lists
from coyote.application.reporting.dna_report_payload import _build_variant_query
from coyote.application.sample.catalog import SampleCatalogService
from coyote.domain.dna.varqueries import build_query
from coyote.domain.exceptions import AppError
from coyote.domain.query_conditions import compile_condition
from coyote_mongo.repositories.samples import SampleRepository
from coyote_mongo.selection import compile_selection
from mongo_test_support.query_settings import _settings
from mongo_test_support.settings import mongo_runtime


@pytest.mark.parametrize("intent", ["somatic", "germline"])
def test_flags_restrict_even_admission_exceptions_and_use_exact_membership(intent):
    from coyote.config.clinical_query_policy import resolved_query_policy

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
    query = compile_selection(build_query("demo", settings, intent=intent, policy=policy))
    assert [row["POS"] for row in collection.find(query)] == [1, 3, 4, 5]
    settings["exclude_flags"] = ["PASS"]
    assert [
        row["POS"]
        for row in collection.find(
            compile_selection(build_query("demo", settings, intent=intent, policy=policy))
        )
    ] == [3, 4, 5]
    settings["exclude_flags"] = []
    assert (
        collection.count_documents(
            compile_selection(build_query("demo", settings, intent=intent, policy=policy))
        )
        == 5
    )


def test_query_conditions_resolve_active_flag_filters():
    node = {
        "type": "predicate",
        "field": "FILTER",
        "operator": "nin",
        "value": {"source": "sample.filters", "key": "exclude_flags"},
    }
    assert compile_selection(
        compile_condition(node, "snv", filter_values={"exclude_flags": ["PASS"]})
    ) == {"FILTER": {"$nin": ["PASS"]}}
    with pytest.raises(ValueError, match="context"):
        compile_selection(compile_condition(node, "snv"))
    with pytest.raises(ValueError, match="Unknown cnv field"):
        compile_selection(compile_condition(node, "cnv", filter_values={"exclude_flags": ["PASS"]}))


@pytest.mark.parametrize("intent", ["somatic", "germline"])
def test_report_query_preserves_flag_filters(intent):
    query = compile_selection(
        _build_variant_query(
            "demo",
            {"_id": "SAMPLE_1"},
            {intent: {"snv": {"exclude_flags": ["WARN_NOVAR"]}}},
            [],
            [],
            [],
            False,
            intent=intent,
        )
    )
    assert {"FILTER": {"$nin": ["WARN_NOVAR"]}} in query["$and"]


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
        SimpleNamespace(
            app=mongo_runtime(), samples_collection=collection, client=collection.database.client
        )
    )
    from coyote_mongo.repositories import samples as repository_module

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
