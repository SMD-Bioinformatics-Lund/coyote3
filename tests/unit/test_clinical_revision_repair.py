"""Revision hashes survive nulls/defaults; repair verifies originals before writing."""

import hashlib
from datetime import datetime, timezone

import mongomock
import pytest
from bson import BSON, ObjectId, decode_all
from bson.codec_options import CodecOptions
from bson.json_util import CANONICAL_JSON_OPTIONS, dumps

from api.infra.mongo.repositories.clinical_rule_sets import (
    build_revision_snapshot,
    verify_revision_snapshot,
)
from scripts.upgrade_from_v3.repair_clinical_rule_revision_hashes import repair
from tests.unit.reporting.test_clinical_rules import _document


def snapshot(*, revision=1, previous=None):
    """Build a synthetic draft snapshot with a cleared content hash."""
    doc = _document().model_dump(mode="python", by_alias=True, exclude_none=True)
    doc.update(_id=ObjectId("000000000000000000000001"), revision=revision, content_hash=None)
    return build_revision_snapshot(
        doc,
        action="draft_updated",
        actor="synthetic",
        occurred_at=datetime.now(timezone.utc),
        reason=None,
        previous_revision_hash=previous,
    )


def old_snapshot(*, revision=1, previous=None):
    """Reproduce the faulty historical writer without changing production verification."""
    result = snapshot(revision=revision, previous=previous)
    payload = {k: v for k, v in result.items() if k != "revision_hash"}
    payload.update(reason=None, previous_revision_hash=previous)
    payload["document"] = dict(payload["document"], content_hash=None)
    result["revision_hash"] = hashlib.sha256(
        dumps(
            payload,
            json_options=CANONICAL_JSON_OPTIONS,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    return result


def test_normalization_precedes_hash_and_survives_bson():
    result = snapshot()
    stored = BSON.encode(result).decode(CodecOptions(tz_aware=True))
    assert verify_revision_snapshot(stored)["revision_hash"] == result["revision_hash"]
    assert "content_hash" not in stored["document"]


def test_repair_verifies_chains_and_preserves_backups(monkeypatch, tmp_path):
    db = mongomock.MongoClient(tz_aware=True).test
    first = old_snapshot()
    second = old_snapshot(revision=2, previous=first["revision_hash"])
    db.clinical_rule_revisions.insert_many([first, second])
    original = list(db.clinical_rule_revisions.find())
    assert repair(db)["verified_serialization_failures"] == 2
    assert list(db.clinical_rule_revisions.find()) == original
    monkeypatch.setattr(
        "scripts.upgrade_from_v3.repair_clinical_rule_revision_hashes.run_transaction",
        lambda client, callback: callback(None),
    )
    backup = tmp_path / "original.bson"
    repair(db, apply=True, backup_file=backup)
    assert decode_all(backup.read_bytes(), CodecOptions(tz_aware=True)) == original
    assert backup.stat().st_mode & 0o777 == 0o600
    repaired = list(db.clinical_rule_revisions.find().sort("revision", 1))
    for item in repaired:
        verify_revision_snapshot(item)
    assert repaired[1]["previous_revision_hash"] == repaired[0]["revision_hash"]
    assert repair(db)["revisions_to_replace"] == 0


@pytest.mark.parametrize("problem", ["unknown_digest", "chain", "report"])
def test_repair_refuses_unexplained_or_referenced_history(problem, tmp_path):
    db = mongomock.MongoClient(tz_aware=True).test
    item = old_snapshot(previous="a" * 64 if problem == "chain" else None)
    if problem == "unknown_digest":
        item["revision_hash"] = "0" * 64
    if problem == "report":
        db.reports.insert_one(
            {
                "clinical_rule_source": {
                    "source": {
                        "rule_set_oid": item["rule_set_oid"],
                    }
                }
            }
        )
    db.clinical_rule_revisions.insert_one(item)
    with pytest.raises(ValueError):
        repair(db, apply=True, backup_file=tmp_path / "refused.bson")
    assert not (tmp_path / "refused.bson").exists()
    assert db.clinical_rule_revisions.find_one()["revision_hash"] == item["revision_hash"]
