"""Retained resource histories remain read-only, complete and scoped to exact identities."""

from types import SimpleNamespace

import mongomock
import pytest

from api.infra.mongo.repositories.assay_configurations import ASPConfigRepository
from api.infra.mongo.repositories.assay_panels import ASPRepository
from api.infra.mongo.repositories.clinical_rule_sets import ClinicalRuleSetRepository
from api.infra.mongo.repositories.gene_lists import ISGLRepository


@pytest.mark.parametrize(
    ("repository_type", "collection_attr", "field"),
    [
        (ASPRepository, "asp_collection", "asp_id"),
        (ASPConfigRepository, "aspc_collection", "aspc_id"),
        (ISGLRepository, "insilico_genelist_collection", "isgl_id"),
    ],
)
def test_history_retains_every_exact_revision_including_retired_only_resources(
    repository_type, collection_attr, field
):
    """History is not capped at list page size and cannot activate an old revision."""
    collection = mongomock.MongoClient().synthetic.resources
    repository = repository_type(SimpleNamespace(**{collection_attr: collection}))
    collection.insert_many(
        [
            {
                field: "synthetic",
                "version": version,
                "is_active": False,
                "description": str(version),
            }
            for version in range(1, 251)
        ]
    )
    collection.insert_one({field: "synthetic-other", "version": 999, "is_active": True})
    before = list(collection.find())
    versions = repository.list_versions("synthetic")
    assert [row["version"] for row in versions] == list(range(250, 0, -1))
    assert not any(row["is_active"] for row in versions)
    assert repository.list_versions("missing") == []
    assert list(collection.find()) == before


def test_reporting_rule_lists_distinguish_current_from_historical_publications():
    """A past published status cannot make a superseded release current again."""
    database = mongomock.MongoClient().synthetic
    repository = ClinicalRuleSetRepository(
        SimpleNamespace(
            clinical_rule_sets_collection=database.rules,
            clinical_rule_revisions_collection=database.revisions,
        )
    )
    database.rules.insert_many(
        [
            {"_id": "current", "status": "published", "active": True, "name": "Synthetic"},
            {"_id": "past", "status": "published", "active": False, "name": "Synthetic"},
            {"_id": "retired", "status": "retired", "active": False, "name": "Synthetic"},
            {"_id": "draft", "status": "draft", "active": False, "name": "Synthetic"},
        ]
    )
    current, total = repository.list_rule_sets(status="published")
    assert total == 1 and current[0]["_id"] == "current"
    historical, total = repository.list_rule_sets(status="retired", search="Synthetic")
    assert total == 2 and {row["_id"] for row in historical} == {"past", "retired"}
    assert database.rules.find_one({"_id": "past"})["status"] == "published"
