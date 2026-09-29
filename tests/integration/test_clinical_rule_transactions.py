"""Clinical rule migration and lifecycle checks on a disposable MongoDB replica set."""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pymongo import MongoClient
from pymongo.collection import Collection

from api.infra.mongo.repositories.clinical_rule_sets import ClinicalRuleSetRepository
from scripts.remove_clinical_engine_version import migrate
from tests.unit.test_remove_clinical_engine_version import seed_database


@pytest.fixture
def database():
    uri = os.getenv("CLINICAL_RULE_TEST_MONGO_URI")
    if not uri:
        pytest.skip("Set CLINICAL_RULE_TEST_MONGO_URI for disposable rule transactions")
    with MongoClient(uri, serverSelectionTimeoutMS=3000, tz_aware=True) as client:
        db = client[f"coyote3_rule_test_{uuid4().hex}"]
        try:
            yield db, seed_database(db)
        finally:
            client.drop_database(db.name)


def test_engine_cleanup_commits_and_is_idempotent(database):
    db, _ = database
    assert migrate(db, apply=True) == {"rules": 1, "revisions": 2}
    assert migrate(db, apply=True) == {"rules": 0, "revisions": 0}


def test_engine_cleanup_rolls_back_all_changes_on_revision_failure(database, monkeypatch):
    db, mapping = database
    original = Collection.replace_one

    def fail_revision(collection, *args, **kwargs):
        if collection.name == mapping["clinical_rule_revisions_collection"]:
            raise RuntimeError("Synthetic revision failure")
        return original(collection, *args, **kwargs)

    monkeypatch.setattr(Collection, "replace_one", fail_revision)
    with pytest.raises(RuntimeError, match="Synthetic revision failure"):
        migrate(db, apply=True)
    assert "minimum_engine_version" in db[mapping["clinical_rule_sets_collection"]].find_one()
    assert (
        db[mapping["clinical_rule_revisions_collection"]].count_documents(
            {"document.minimum_engine_version": {"$exists": True}}
        )
        == 2
    )


@pytest.mark.parametrize("operation", ["transition", "publish"])
def test_lifecycle_refuses_stale_validation_revision(database, operation):
    db, mapping = database
    migrate(db, apply=True)
    repository = ClinicalRuleSetRepository(
        SimpleNamespace(
            client=db.client,
            clinical_rule_sets_collection=db[mapping["clinical_rule_sets_collection"]],
            clinical_rule_revisions_collection=db[mapping["clinical_rule_revisions_collection"]],
        )
    )
    document = repository.get_collection().find_one()
    event = {"action": "submitted", "actor": "synthetic", "occurred_at": document["updated_at"]}
    kwargs = {
        "expected_revision": document["revision"] - 1,
        "changes": {"status": "submitted"},
        "event": event,
    }
    if operation == "transition":
        kwargs["from_statuses"] = {"draft"}
    else:
        repository.get_collection().update_one(
            {"_id": document["_id"]}, {"$set": {"status": "approved"}}
        )
    assert getattr(repository, operation)(document["_id"], **kwargs) is None
    assert repository.get_collection().find_one()["revision"] == document["revision"]
    assert db[mapping["clinical_rule_revisions_collection"]].count_documents({}) == 2
