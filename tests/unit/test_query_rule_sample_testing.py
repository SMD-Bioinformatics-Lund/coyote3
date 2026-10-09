"""Exercise stored-sample comparisons using synthetic repositories only."""

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest

from api.application import query_rule_testing as testing
from api.contracts.schemas.query_rules import (
    QueryRuleDoc,
    QueryRulePreview,
    QueryRuleSampleResult,
    QueryRuleScope,
)
from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repositories.query_rules import QueryRuleRepository


@pytest.fixture
def context(monkeypatch):
    db = mongomock.MongoClient().synthetic
    repos = {}
    for name in ["variant", "copy_number_variant", "translocation", "fusion"]:
        repo = BaseRepository(SimpleNamespace())
        repo.set_collection(db[name])
        repos[name + "_repository"] = repo
    panel = {
        "asp_id": "example",
        "asp_group": "group",
        "asp_category": "dna",
        "asp_family": "wgs",
        "covered_genes": [],
    }
    config = {
        "asp_group": "group",
        "analysis_types": ["SNV", "CNV", "TRANSLOCATION", "FUSION"],
        "filters": {},
    }
    store = SimpleNamespace(
        **repos,
        query_rule_repository=QueryRuleRepository(
            SimpleNamespace(
                query_rule_sets_collection=db.rules,
                query_rule_revisions_collection=db.query_rule_revisions,
            )
        ),
        assay_group_repository=SimpleNamespace(get=lambda key: {"group_id": key}),
        assay_panel_repository=SimpleNamespace(
            get_asp=lambda *a, **kw: panel, get_all_asps=lambda **kw: [panel]
        ),
        assay_subpanel_repository=SimpleNamespace(),
        assay_configuration_repository=SimpleNamespace(),
        gene_list_repository=SimpleNamespace(get_isgl_by_ids=lambda ids: {}),
        vep_metadata_repository=SimpleNamespace(
            get_consequence_group_map=lambda *args: {"missense": ["missense_variant"]}
        ),
        sample_repository=Mock(),
    )
    sample = {
        "_id": "sample",
        "name": "SYNTHETIC",
        "asp_id": "example",
        "subpanel_id": "base",
        "omics_layer": "dna",
        "environment": "validation",
        "ingest_status": "ready",
        "analysis_intents": ["somatic"],
        "database_versions": {"vep": "115"},
    }
    monkeypatch.setattr(testing, "get_formatted_assay_config", lambda *a, **kw: config)
    return testing.QueryRuleTestingService(store), db, sample, config


def request(analysis, field, value):
    return QueryRulePreview(
        scope=QueryRuleScope(assay_group="group", analysis=analysis),
        content={
            "exceptions": [
                {
                    "id": "exclude_example",
                    "mode": "exclude",
                    "condition": {
                        "type": "predicate",
                        "field": field,
                        "operator": "eq",
                        "value": value,
                    },
                }
            ]
        },
    )


def preview(service, req, sample):
    return service.preview(
        req, sample, allowed_asp_ids=["example"], allowed_environments=["validation"]
    )


@pytest.mark.parametrize(
    "analysis,repository,field,rows",
    [
        (
            "snv",
            "variant",
            "CHROM",
            [
                {
                    "CHROM": "1",
                    "GT": [{"type": "case", "AF": 0.2, "DP": 1000, "VD": 200}],
                    "consequence_terms": ["missense_variant"],
                },
                {
                    "CHROM": "2",
                    "GT": [{"type": "case", "AF": 0.2, "DP": 1000, "VD": 200}],
                    "consequence_terms": ["missense_variant"],
                },
            ],
        ),
        (
            "cnv",
            "copy_number_variant",
            "chr",
            [
                {"chr": "1", "start": 1, "end": 1001, "size": 1000, "ratio": 1.0, "type": "AMP"},
                {"chr": "2", "start": 1, "end": 1001, "size": 1000, "ratio": 1.0, "type": "AMP"},
            ],
        ),
        ("translocation", "translocation", "CHROM", [{"CHROM": "1"}, {"CHROM": "2"}]),
        (
            "fusion",
            "fusion",
            "gene1",
            [
                {
                    "gene1": "1",
                    "gene2": "ALK",
                    "calls": [{"caller": "arriba", "spanreads": 10, "spanpairs": 10}],
                },
                {
                    "gene1": "2",
                    "gene2": "ALK",
                    "calls": [{"caller": "arriba", "spanreads": 10, "spanpairs": 10}],
                },
            ],
        ),
    ],
)
def test_sample_comparison_uses_real_query_builders_without_writes(
    context, monkeypatch, analysis, repository, field, rows
):
    service, db, sample, config = context
    config["filters"] = {
        "somatic": {
            "snv": {"vep_consequences": ["missense"]},
            "cnv": {
                "cnv_loss_cutoff": -0.3,
                "cnv_gain_cutoff": 0.3,
                "min_cnv_size": 100,
                "max_cnv_size": 50000000,
            },
        }
    }
    if analysis == "fusion":
        sample["omics_layer"] = "rna"
        config["filters"] = {}
        workflow = object.__new__(testing.RNAWorkflowService)
        workflow.gene_list_repository = service.store.gene_list_repository
        monkeypatch.setattr(testing.RNAWorkflowService, "from_store", lambda store: workflow)
    docs = [{"_id": str(index), "SAMPLE_ID": "sample", **row} for index, row in enumerate(rows)]
    db[repository].insert_many(docs + [{"_id": "other", "SAMPLE_ID": "different", **rows[0]}])
    before = deepcopy(sample)
    collection = db[repository]
    original_find = collection.find
    executed_queries = []

    def capture_find(query, *args, **kwargs):
        """Capture the exact predicates submitted to the in-memory Mongo boundary."""
        executed_queries.append(deepcopy(query))
        return original_find(query, *args, **kwargs)

    monkeypatch.setattr(collection, "find", capture_find)
    result = preview(service, request(analysis, field, "1"), sample)
    QueryRuleSampleResult.model_validate(result)
    assert result["published_query"] == executed_queries[0]
    assert result["draft_query"] == executed_queries[1]
    assert result["draft_query"]["$and"][0] == {"SAMPLE_ID": "sample"}
    assert result["published_count"] == 2
    assert result["draft_count"] == 1
    assert result["removed_count"] == 1 and result["removed"][0]["id"] == "0"
    assert result["added_count"] == 0 and result["persisted"] is False
    assert sample == before
    assert db[repository].count_documents({}) == 3
    assert db.rules.count_documents({}) == 0
    assert not service.store.sample_repository.method_calls


@pytest.mark.parametrize("change", [{"environment": "production"}, {"asp_id": "other"}])
def test_preview_denies_sample_scope_before_loading_configuration(context, change):
    service, _, sample, _ = context
    with pytest.raises(AppError):
        preview(service, request("snv", "CHROM", "1"), {**sample, **change})


def test_preview_rejects_unready_sample_and_unavailable_analysis(context):
    service, _, sample, config = context
    with pytest.raises(AppError):
        preview(service, request("snv", "CHROM", "1"), {**sample, "ingest_status": "loading"})
    config["analysis_types"] = []
    with pytest.raises(AppError):
        preview(service, request("snv", "CHROM", "1"), sample)


def test_group_draft_does_not_override_published_assay_child(context):
    service, db, _, _ = context
    scope = QueryRuleScope(assay_group="group", asp_id="example", analysis="snv")
    now = datetime.now(timezone.utc)
    child = QueryRuleDoc(
        scope=scope,
        scope_key=scope.key(),
        name="Child",
        reason="Synthetic",
        content={"exceptions": []},
        version=3,
        status="published",
        created_by="a",
        updated_by="b",
        created_on=now,
        updated_on=now,
    )
    db.rules.insert_one(child.model_dump(by_alias=True))
    proposed = service._proposed_service(request("snv", "CHROM", "1")).resolve(scope)
    assert proposed.exceptions == []
    assert proposed.lineage[-1]["source"] == scope.key()
    assert db.rules.count_documents({}) == 1


def test_search_intersects_access_and_never_treats_empty_assays_as_unrestricted(context):
    service, _, _, _ = context
    result = service.search_samples(
        scope=QueryRuleScope(analysis="snv"),
        search="",
        page=1,
        allowed_asp_ids=[],
        allowed_environments=["validation"],
    )
    assert result["items"] == []
    service.store.sample_repository.search_samples_for_admin.assert_not_called()


def test_repository_forces_sample_scope_even_for_a_broad_predicate(context):
    service, db, _, _ = context
    db.variant.insert_many([{"SAMPLE_ID": "sample"}, {"SAMPLE_ID": "other"}])
    assert len(service.store.variant_repository.preview_sample_findings("sample", {})) == 1


def test_candidate_overflow_rejects_partial_comparison(context):
    service, _, sample, _ = context
    service.store.translocation_repository.preview_sample_findings = Mock(return_value=[{}] * 10001)
    with pytest.raises(AppError, match="10000"):
        preview(service, request("translocation", "CHROM", "1"), sample)


def test_sample_preview_resolves_references_from_saved_filters(context):
    service, db, sample, config = context
    config["filters"] = {"somatic": {"snv": {"vep_consequences": ["missense"]}}}
    for index, af in enumerate([0.2, 0.3]):
        db.variant.insert_one(
            {
                "_id": str(index),
                "SAMPLE_ID": "sample",
                "consequence_terms": ["missense_variant"],
                "GT": [{"type": "case", "AF": af, "DP": 1000, "VD": 200}],
            }
        )
    req = request("snv", "GT.AF", {"source": "sample.filters", "key": "min_freq"})
    sample["filters"] = {"somatic": {"snv": {"min_freq": 0.2, "vep_consequences": ["missense"]}}}
    assert preview(service, req, sample)["removed"][0]["id"] == "0"
    sample["filters"]["somatic"]["snv"]["min_freq"] = 0.3
    assert preview(service, req, sample)["removed"][0]["id"] == "1"
    assert req.content.exceptions[0]["condition"]["value"] == {
        "source": "sample.filters",
        "key": "min_freq",
    }


def test_germline_draft_is_tested_against_somatic_sample_selection(context):
    service, db, sample, config = context
    config["filters"] = {"somatic": {"snv": {"vep_consequences": ["missense"]}}}
    db.variant.insert_one({"_id": "germline-finding", "SAMPLE_ID": "sample", "FILTER": "GERMLINE"})
    db.variant.insert_one({"_id": "other-sample", "SAMPLE_ID": "different", "FILTER": "GERMLINE"})
    req = QueryRulePreview(
        scope=QueryRuleScope(assay_group="group", analysis="snv", intent="germline"),
        content={
            "evidence_mode": "exception_only",
            "exceptions": [
                {
                    "id": "marker",
                    "mode": "admit",
                    "condition": {
                        "type": "predicate",
                        "field": "FILTER",
                        "operator": "eq",
                        "value": "GERMLINE",
                    },
                }
            ],
        },
    )
    result = preview(service, req, sample)
    assert result["intent"] == "somatic"
    assert result["published_count"] == 0
    assert result["draft_count"] == 1
    assert result["added"][0]["id"] == "germline-finding"
    assert sample["analysis_intents"] == ["somatic"]
    excluded = req.model_copy(deep=True)
    excluded.content.exceptions.append(
        {
            "id": "remove_marker",
            "mode": "exclude",
            "condition": {
                "type": "predicate",
                "field": "FILTER",
                "operator": "eq",
                "value": "GERMLINE",
            },
        }
    )
    assert preview(service, excluded, sample)["draft_count"] == 0


def test_search_passes_assay_and_environment_intersection(context):
    service, _, _, _ = context
    service.store.sample_repository.search_samples_for_admin.return_value = ([], 0)
    service.search_samples(
        scope=QueryRuleScope(assay_group="group", analysis="snv"),
        search="SYNTHETIC",
        page=1,
        allowed_asp_ids=["example", "other"],
        allowed_environments=["validation"],
    )
    params = service.store.sample_repository.search_samples_for_admin.call_args.kwargs
    assert params["asp_ids"] == ["example"]
    assert params["environments"] == ["validation"]
    assert params["ready_only"] is True
