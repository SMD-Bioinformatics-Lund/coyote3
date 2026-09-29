"""Development-only cleanup preserves integrity and refuses report history rewrites."""

import hashlib
import json
from copy import deepcopy

import mongomock
import pytest
from bson import BSON
from bson.codec_options import CodecOptions
from bson.json_util import CANONICAL_JSON_OPTIONS, dumps

from api.application.reporting.clinical_rules.validation import canonical_content, content_hash
from api.config.loaders.collections import load_collection_section
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
from api.infra.mongo.repositories.clinical_rule_sets import (
    build_revision_snapshot,
    verify_revision_snapshot,
)
from scripts import remove_clinical_engine_version as migration
from tests.unit.reporting.test_clinical_rules import _document


def seed_database(db):
    """Create two linked old-format revisions and a matching current document."""
    mapping = load_collection_section("primary")
    document = _document(status="draft", active=False)
    previous = None
    for revision in (1, 2):
        document.revision = revision
        old_content = canonical_content(document)
        old_content["minimum_engine_version"] = 3
        document.content_hash = hashlib.sha256(
            json.dumps(
                old_content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        snapshot = build_revision_snapshot(
            document.model_dump(mode="python", by_alias=True),
            action="draft_saved",
            actor="synthetic",
            occurred_at=document.updated_at,
            reason=None,
            previous_revision_hash=previous,
        )
        snapshot.pop("revision_hash")
        snapshot.pop("_id", None)
        snapshot["reason"] = None
        snapshot["previous_revision_hash"] = previous
        snapshot["document"]["minimum_engine_version"] = 3
        snapshot = BSON.encode(snapshot).decode(codec_options=CodecOptions(tz_aware=True))
        snapshot["revision_hash"] = hashlib.sha256(
            dumps(
                snapshot, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest()
        previous = snapshot["revision_hash"]
        db[mapping["clinical_rule_revisions_collection"]].insert_one(snapshot)
    source = document.model_dump(mode="python", by_alias=True)
    source["minimum_engine_version"] = 3
    db[mapping["clinical_rule_sets_collection"]].insert_one(source)
    return mapping


@pytest.fixture
def database(monkeypatch):
    db = mongomock.MongoClient(tz_aware=True).test
    mapping = seed_database(db)
    monkeypatch.setattr(migration, "run_transaction", lambda client, callback: callback(None))
    return db, mapping


def test_cleanup_is_dry_by_default_and_idempotent(database):
    db, mapping = database
    rules = db[mapping["clinical_rule_sets_collection"]]
    original = deepcopy(rules.find_one())
    assert migration.migrate(db) == {"rules": 1, "revisions": 2}
    assert rules.find_one() == original
    assert migration.migrate(db, apply=True) == {"rules": 1, "revisions": 2}
    updated = rules.find_one()
    assert "minimum_engine_version" not in updated
    assert updated["content_hash"] == content_hash(ClinicalRuleSetDoc.model_validate(updated))
    previous = None
    for snapshot in db[mapping["clinical_rule_revisions_collection"]].find().sort("revision", 1):
        verified = verify_revision_snapshot(snapshot)
        assert verified.get("previous_revision_hash") == previous
        previous = verified["revision_hash"]
    assert migration.migrate(db, apply=True) == {"rules": 0, "revisions": 0}


def test_cleanup_refuses_saved_reports(database):
    db, mapping = database
    db[mapping["reports_collection"]].insert_one({"synthetic": True})
    with pytest.raises(ValueError, match="Saved reports exist"):
        migration.migrate(db, apply=True)
    assert "minimum_engine_version" in db[mapping["clinical_rule_sets_collection"]].find_one()


@pytest.mark.parametrize(
    "collection,field",
    [
        ("clinical_rule_sets_collection", "content_hash"),
        ("clinical_rule_revisions_collection", "revision_hash"),
        ("clinical_rule_revisions_collection", "previous_revision_hash"),
    ],
)
def test_cleanup_refuses_corruption(database, collection, field):
    db, mapping = database
    db[mapping[collection]].update_one({}, {"$set": {field: "corrupt"}})
    with pytest.raises(ValueError, match="integrity|chain"):
        migration.migrate(db, apply=True)
    assert "minimum_engine_version" in db[mapping["clinical_rule_sets_collection"]].find_one()
