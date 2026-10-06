"""Clinical rule lifecycle checks on a disposable MongoDB replica set."""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pymongo import MongoClient

from api.config.loaders.collections import load_collection_section
from api.infra.mongo.repositories.clinical_rule_sets import (
    ClinicalRuleSetRepository,
    build_revision_snapshot,
)
from tests.unit.reporting.test_clinical_rules import _document


def seed_database(db):
    """Create current-format rule revisions without a development cleanup dependency."""
    mapping = load_collection_section("primary")
    document = _document(status="draft", active=False)
    previous = None
    for revision in (1, 2):
        document.revision = revision
        snapshot = build_revision_snapshot(
            document.model_dump(mode="python", by_alias=True),
            action="draft_saved",
            actor="synthetic",
            occurred_at=document.updated_at,
            reason=None,
            previous_revision_hash=previous,
        )
        previous = snapshot["revision_hash"]
        db[mapping["clinical_rule_revisions_collection"]].insert_one(snapshot)
    db[mapping["clinical_rule_sets_collection"]].insert_one(
        document.model_dump(mode="python", by_alias=True)
    )
    return mapping


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


@pytest.mark.parametrize("operation", ["transition", "publish"])
def test_lifecycle_refuses_stale_validation_revision(database, operation):
    db, mapping = database
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
