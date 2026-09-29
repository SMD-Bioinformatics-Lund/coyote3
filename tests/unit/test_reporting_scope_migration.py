"""Configuration-only migration and duplicate-scope preflight tests."""

import mongomock
import pytest

from scripts.migrate_reporting_rule_resolution import migrate


def test_dry_run_apply_idempotency_and_historical_isolation(monkeypatch):
    db = mongomock.MongoClient().test
    db.clinical_rule_sets.insert_one(
        {
            "rule_set_id": "assay__base__en",
            "status": "published",
            "active": True,
            "scope": {"asp_id": "assay", "subpanel_id": "base", "analyte": "dna", "language": "en"},
        }
    )
    reporting = {"clinical_rule_set_id": "assay__base__en", "report_sections": ["SNV"]}
    db.asp_configs.insert_one({"reporting": reporting, "version": 7})
    db.assay_setups.insert_one(
        {"status": "draft", "content": {"configurations": [{"reporting": reporting}]}}
    )
    db.reports.insert_one({"reporting": reporting})
    original_reports = list(db.reports.find())
    original_rules = list(db.clinical_rule_sets.find())
    assert migrate(db) == {
        "asp_configs": 1,
        "assay_setups": 1,
        "rule_documents": 0,
        "rule_revisions": 0,
        "selection_changes": 0,
    }
    assert db.asp_configs.find_one()["reporting"] == reporting
    monkeypatch.setattr(
        "scripts.migrate_reporting_rule_resolution.run_transaction",
        lambda _client, callback: callback(None),
    )
    migrate(db, apply=True)
    assert db.asp_configs.find_one()["reporting"] == {"language": "en", "report_sections": ["SNV"]}
    assert db.asp_configs.find_one()["version"] == 7
    assert list(db.reports.find()) == original_reports
    assert list(db.clinical_rule_sets.find()) == original_rules
    assert not any(migrate(db).values())


def test_invalid_revision_checksum_prevents_all_configuration_writes():
    from datetime import datetime, timezone

    from api.infra.mongo.repositories.clinical_rule_sets import build_revision_snapshot
    from tests.unit.reporting.test_clinical_rules import _document

    db = mongomock.MongoClient(tz_aware=True).test
    doc = _document().model_dump(mode="python", by_alias=True, exclude_none=True)
    snapshot = build_revision_snapshot(
        doc,
        action="created",
        actor="synthetic",
        occurred_at=datetime.now(timezone.utc),
        reason=None,
        previous_revision_hash=None,
    )
    snapshot["revision_hash"] = "0" * 64
    db.clinical_rule_revisions.insert_one(snapshot)
    db.asp_configs.insert_one({"reporting": {}})
    with pytest.raises(RuntimeError, match="integrity verification failed"):
        migrate(db, apply=True)
    assert db.asp_configs.find_one()["reporting"] == {}


def test_obsolete_binding_is_not_an_accepted_reporting_fact():
    from pydantic import ValidationError

    from api.application.reporting.clinical_rules.facts import PreparedAspcReportingFacts

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        PreparedAspcReportingFacts.model_validate({"clinical_rule_set_id": "obsolete"})


def test_missing_bound_rule_stops_before_writes():
    db = mongomock.MongoClient().test
    db.asp_configs.insert_one({"reporting": {"clinical_rule_set_id": "missing"}})
    with pytest.raises(ValueError, match="Cannot determine"):
        migrate(db, apply=True)
    assert db.asp_configs.find_one()["reporting"] == {"clinical_rule_set_id": "missing"}


def test_duplicate_published_scope_stops_before_writes():
    db = mongomock.MongoClient().test
    for identity in ["a", "b"]:
        db.clinical_rule_sets.insert_one(
            {
                "rule_set_id": identity,
                "status": "published",
                "active": True,
                "scope": {
                    "asp_id": "assay",
                    "subpanel_id": "base",
                    "analyte": "dna",
                    "language": "sv",
                },
            }
        )
    with pytest.raises(ValueError, match="Ambiguous"):
        migrate(db)


def test_scope_index_allows_drafts_but_rejects_two_active_releases(monkeypatch):
    from pymongo.errors import DuplicateKeyError

    db = mongomock.MongoClient().test
    monkeypatch.setattr(
        "scripts.migrate_reporting_rule_resolution.run_transaction",
        lambda _client, callback: callback(None),
    )
    migrate(db, apply=True)
    row = {
        "scope": {"asp_id": "a", "subpanel_id": "base", "analyte": "dna", "language": "sv"},
        "status": "published",
        "active": True,
    }
    db.clinical_rule_sets.insert_one(dict(row))
    db.clinical_rule_sets.insert_one(dict(row, status="draft", active=False))
    with pytest.raises(DuplicateKeyError):
        db.clinical_rule_sets.insert_one(dict(row))


def test_submitted_setup_blocks_migration():
    db = mongomock.MongoClient().test
    db.assay_setups.insert_one(
        {"status": "submitted", "content": {"configurations": [{"reporting": {}}]}}
    )
    with pytest.raises(ValueError, match="Return in-review"):
        migrate(db)


def test_missing_active_reporting_scope_blocks_preflight():
    db = mongomock.MongoClient().test
    db.asp_configs.insert_one(
        {
            "asp_id": "assay",
            "asp_category": "DNA",
            "is_active": True,
            "reporting": {"language": "sv", "report_sections": ["SNV"]},
        }
    )
    with pytest.raises(ValueError, match="No active published"):
        migrate(db)


def test_migrates_embedded_facts_and_revision_hash_chain(monkeypatch):
    from datetime import datetime, timezone

    from api.application.reporting.clinical_rules.validation import content_hash
    from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
    from api.infra.mongo.repositories.clinical_rule_sets import (
        build_revision_snapshot,
        verify_revision_snapshot,
    )
    from tests.unit.reporting.test_clinical_rules import _context, _document

    db = mongomock.MongoClient(tz_aware=True).test
    doc = _document(status="published", active=True).model_dump(
        mode="python", by_alias=True, exclude_none=True
    )
    facts = _context().model_dump(mode="python")
    facts["aspc"]["reporting"]["clinical_rule_set_id"] = doc["rule_set_id"]
    doc["test_cases"] = [
        {
            "test_id": "old",
            "name": "Old case",
            "facts": facts,
            "expected_rule_ids": [],
            "expected_sections": {},
        }
    ]
    doc["content_hash"] = content_hash(ClinicalRuleSetDoc.model_validate(doc))
    snapshot = build_revision_snapshot(
        doc,
        action="published",
        actor="synthetic",
        occurred_at=datetime.now(timezone.utc),
        reason=None,
        previous_revision_hash=None,
    )
    db.clinical_rule_sets.insert_one(doc)
    db.clinical_rule_revisions.insert_one(snapshot)
    monkeypatch.setattr(
        "scripts.migrate_reporting_rule_resolution.run_transaction",
        lambda _client, callback: callback(None),
    )
    assert migrate(db)["rule_documents"] == 1
    assert (
        "clinical_rule_set_id"
        in db.clinical_rule_sets.find_one()["test_cases"][0]["facts"]["aspc"]["reporting"]
    )
    db.reports.insert_one({"clinical_rule_source": {"source": {"rule_set_oid": str(doc["_id"])}}})
    with pytest.raises(ValueError, match="Saved reports"):
        migrate(db, apply=True)
    db.reports.delete_many({})
    migrate(db, apply=True)
    changed = db.clinical_rule_sets.find_one()
    assert "clinical_rule_set_id" not in changed["test_cases"][0]["facts"]["aspc"]["reporting"]
    assert changed["content_hash"] == content_hash(ClinicalRuleSetDoc.model_validate(changed))
    verify_revision_snapshot(db.clinical_rule_revisions.find_one())
    assert not any(migrate(db).values())
