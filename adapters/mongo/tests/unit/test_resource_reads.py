"""Synthetic metadata reads exercise scope, joins and aggregate pagination."""

from datetime import datetime
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from coyote.application.operations.resource_reads import ResourceReadScope
from coyote.domain.exceptions import AppError
from coyote_contracts.retrieval import ReadResource, ResourceReadQuery
from coyote_mongo.repositories.resource_reads import MongoResourceReadRepository


@pytest.fixture
def catalog():
    database = mongomock.MongoClient().isolated_reads
    store = SimpleNamespace(
        **{
            name: database[name]
            for name in (
                "asp_collection",
                "aspc_collection",
                "samples_collection",
                "insilico_genelist_collection",
                "assay_groups_collection",
                "diagnoses_collection",
                "diagnosis_associations_collection",
            )
        }
    )
    config_a, config_b, config_cross = ObjectId(), ObjectId(), ObjectId()
    store.asp_collection.insert_many(
        [
            {"asp_id": "a", "asp_group": "dna", "version": 1, "is_active": False},
            {
                "asp_id": "a",
                "asp_group": "dna",
                "version": 2,
                "is_active": True,
                "expected_files": ["vcf", "bam"],
            },
            {
                "asp_id": "b",
                "asp_group": "rna",
                "version": 1,
                "is_active": True,
                "expected_files": ["bam"],
            },
        ]
    )
    store.aspc_collection.insert_many(
        [
            {
                "_id": config_a,
                "aspc_id": "a-prod",
                "asp_id": "a",
                "environment": "production",
                "is_active": False,
                "version": 1,
                "reporting": {"report_sections": ["snvs"]},
            },
            {
                "_id": config_b,
                "aspc_id": "b-dev",
                "asp_id": "b",
                "environment": "development",
                "is_active": True,
                "version": 1,
            },
            {
                "_id": config_cross,
                "aspc_id": "a-dev",
                "asp_id": "a",
                "environment": "development",
                "is_active": True,
                "version": 1,
            },
        ]
    )
    store.samples_collection.insert_many(
        [
            {
                "name": "a1",
                "asp_id": "a",
                "environment": "production",
                "current_aspc_id": config_a,
                "reported": False,
                "diagnosis_id": None,
                "time_added": datetime(2026, 1, 1),
                "secret": "never returned",
            },
            {
                "name": "a2",
                "asp_id": "a",
                "environment": "production",
                "current_aspc_id": str(config_a),
                "reported": True,
            },
            {
                "name": "a3",
                "asp_id": "a",
                "environment": "development",
                "current_aspc_id": config_cross,
                "reported": False,
            },
            {
                "name": "b1",
                "asp_id": "b",
                "environment": "development",
                "current_aspc_id": config_b,
                "reported": False,
            },
            {"name": "b2", "asp_id": "b", "environment": "production", "reported": False},
            {
                "name": "bad-link",
                "asp_id": "a",
                "environment": "production",
                "current_aspc_id": config_b,
            },
        ]
    )
    scope = ResourceReadScope(
        grants=[
            {"asp_id": "a", "environments": ["production"]},
            {"asp_id": "b", "environments": ["development"]},
        ]
    )
    return MongoResourceReadRepository(store), store, scope


def read(catalog, resource="samples", **options):
    repository, _, scope = catalog
    return repository.query(
        ReadResource(resource), ResourceReadQuery.model_validate(options), scope
    )


def test_exact_pairs_apply_to_records_ids_counts_and_exists(catalog):
    result = read(catalog, operation="ids", per_page=2)
    assert result.items == ["a1", "a2"]
    assert result.total == 4 and result.has_next
    assert read(catalog, operation="ids", page=2, per_page=2).items == ["b1", "bad-link"]
    assert read(catalog, operation="count").count == 4
    assert read(catalog, operation="exists", filters={"name": "a3"}).exists is False
    assert read(catalog, operation="exists", filters={"name": "b2"}).exists is False
    assert read(catalog, operation="exists", filters={"name": "b1"}).exists is True


def test_no_grants_fail_closed_and_superuser_is_unscoped(catalog):
    repository, _, _ = catalog
    query = ResourceReadQuery(operation="count")
    assert repository.query(ReadResource.SAMPLES, query, ResourceReadScope(grants=[])).count == 0
    assert repository.query(ReadResource.SAMPLES, query, ResourceReadScope(grants=None)).count == 6


def test_groups_use_authoritative_assay_and_scope_before_count(catalog):
    repository, _, scope = catalog
    restricted = ResourceReadScope(grants=scope.grants, groups=("dna",))
    assert (
        repository.query(
            ReadResource.SAMPLES, ResourceReadQuery(operation="count"), restricted
        ).count
        == 3
    )
    assert read(catalog, filters={"asp_group": "rna"}, fields=["name", "asp_group"]).items == [
        {"name": "b1", "asp_group": "rna"}
    ]


def test_null_false_and_missing_have_different_filter_behavior(catalog):
    assert read(catalog, operation="ids", filters={"reported": False}).items == ["a1", "b1"]
    assert read(catalog, operation="ids", filters={"diagnosis_id": None}).items == ["a1"]
    assert read(catalog, operation="distinct", field="reported").items == [False, True]
    assert read(catalog, filters={"name": "a1"}, fields=["reported", "version"]).items == [
        {"reported": False, "version": None}
    ]
    assert "secret" not in read(catalog, filters={"name": "a1"}).items[0]


def test_multiple_filters_ranges_sort_and_distinct_ids(catalog):
    assert read(
        catalog,
        operation="ids",
        filters={"asp_id": {"in": ["a"]}, "time_added": {"gte": "2025-12-31T00:00:00Z"}},
    ).items == ["a1"]
    page = read(
        catalog,
        resource="asp",
        fields=["asp_id", "version"],
        sort="version",
        descending=True,
        per_page=1,
    )
    assert page.items == [{"asp_id": "a", "version": 2}]
    assert page.total == 3
    assert read(catalog, resource="asp", operation="ids").items == ["a", "b"]
    assert read(
        catalog, resource="asp", operation="distinct", field="expected_files", per_page=1
    ).items == ["bam"]
    assert read(
        catalog, resource="asp", operation="distinct", field="expected_files", page=2, per_page=1
    ).items == ["vcf"]


def test_related_metadata_uses_exact_revision_and_same_scope(catalog):
    result = read(
        catalog, filters={"name": "a1"}, fields=["name"], include=["assay", "configuration"]
    )
    related = result.items[0]["related"]
    assert related["assay"]["version"] == 2
    assert related["configuration"]["is_active"] is False
    assert related["configuration"]["report_sections"] == ["snvs"]
    assert "_id" not in related["configuration"]
    assert (
        read(catalog, filters={"name": "bad-link"}, include=["configuration"]).items[0]["related"][
            "configuration"
        ]
        is None
    )


def test_cross_resource_filters_use_same_scope_for_every_operation(catalog):
    options = {
        "related_filters": {"configuration": {"is_active": False}, "assay": {"asp_group": "dna"}}
    }
    assert read(catalog, operation="ids", **options).items == ["a1", "a2"]
    assert read(catalog, operation="count", **options).count == 2
    assert read(catalog, operation="exists", filters={"name": "b1"}, **options).exists is False
    assert read(
        catalog, operation="ids", related_filters={"configuration": {"environment": "development"}}
    ).items == ["b1"]
    assert (
        read(catalog, operation="ids", related_filters={"assay": {"is_active": False}}).items == []
    )


def test_reference_catalogs_and_derived_values(catalog):
    _, store, _ = catalog
    store.insilico_genelist_collection.insert_one(
        {"isgl_id": "panel", "genes": ["A", "B"], "asp_ids": ["a"], "is_active": False}
    )
    store.diagnoses_collection.insert_one({"diagnosis_id": "base", "version": 1, "is_active": True})
    store.diagnosis_associations_collection.insert_many(
        [
            {"diagnosis_id": "base", "asp_id": "a", "is_current": True},
            {"diagnosis_id": "base", "asp_id": "b", "is_current": False},
        ]
    )
    assert read(
        catalog,
        resource="isgl",
        filters={"gene_count": {"gte": 2}},
        fields=["isgl_id", "gene_count"],
    ).items == [{"isgl_id": "panel", "gene_count": 2}]
    assert read(catalog, resource="diagnoses", operation="distinct", field="asp_ids").items == ["a"]


def test_distinct_retains_explicit_null_but_excludes_absent_and_empty_arrays(catalog):
    _, store, _ = catalog
    store.asp_collection.insert_many(
        [
            {"asp_id": "a", "version": 3, "expected_files": []},
            {"asp_id": "a", "version": 4, "expected_files": None},
        ]
    )
    assert read(catalog, resource="asp", operation="distinct", field="expected_files").items == [
        None,
        "bam",
        "vcf",
    ]
    assert read(catalog, operation="distinct", field="diagnosis_id").items == [None]


def test_related_predicates_are_bounded_and_revision_strings_are_resolved(catalog):
    _, store, _ = catalog
    linked = read(catalog, filters={"name": "a2"}, include=["configuration"])
    assert linked.items[0]["related"]["configuration"]["aspc_id"] == "a-prod"
    store.aspc_collection.insert_many(
        [
            {
                "aspc_id": f"revision-{number}",
                "asp_id": "a",
                "environment": "production",
                "is_active": True,
            }
            for number in range(1001)
        ]
    )
    with pytest.raises(AppError) as error:
        read(catalog, operation="count", related_filters={"configuration": {"is_active": True}})
    assert error.value.status_code == 422


@pytest.mark.parametrize(
    "update",
    [
        {"per_page": 1000000},
        {"filters": {"reported": {"$ne": True}}},
    ],
)
def test_adapter_revalidates_constructed_query_models(catalog, update):
    repository, _, scope = catalog
    with pytest.raises(ValueError):
        repository.query(ReadResource.SAMPLES, ResourceReadQuery().model_copy(update=update), scope)
