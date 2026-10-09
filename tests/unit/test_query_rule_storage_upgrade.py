"""Synthetic coverage for query-rule identity migration and immutable baselines."""

from datetime import datetime, timezone

import mongomock
import pytest

from api.contracts.schemas.query_rules import QueryRuleDoc
from scripts.database import upgrade_query_rule_storage as migration


def legacy_rule():
    """Return a synthetic pre-migration group policy."""
    now = datetime.now(timezone.utc)
    return {
        "scope": {"assay_group": "example", "analysis": "snv", "intent": "somatic"},
        "scope_key": "example:*:*:snv:somatic",
        "name": "Old name",
        "content": {"evidence_mode": None, "exceptions": []},
        "reason": "Synthetic",
        "version": 1,
        "revision": 1,
        "status": "draft",
        "created_by": "tester",
        "updated_by": "tester",
        "created_on": now,
        "updated_on": now,
    }


def test_upgrade_plans_then_preserves_content_and_is_idempotent(tmp_path, monkeypatch):
    db = mongomock.MongoClient().synthetic
    original = legacy_rule()
    db.query_rule_sets.insert_one(original)
    monkeypatch.setattr(migration, "run_transaction", lambda client, action: action(None))
    monkeypatch.setattr(migration, "enqueue_audit", lambda *args, **kwargs: None)
    assert migration.upgrade(db, actor="tester")["versions"] == 1
    assert db.query_rule_sets.find_one()["name"] == "Old name"
    backup = tmp_path / "backup.json"
    migration.upgrade(db, actor="tester", apply=True, backup=backup)
    result = db.query_rule_sets.find_one()
    QueryRuleDoc.model_validate(result)
    assert result["query_id"] == "example__all__base__somatic_snvs"
    assert result["content"]["exceptions"] == original["content"]["exceptions"]
    assert result["status"] == "draft" and result["version"] == 1
    assert result["revision"] == 2
    assert db.query_rule_revisions.count_documents({}) == 1
    assert backup.stat().st_mode & 0o777 == 0o600
    assert migration.upgrade(db, actor="tester", apply=True)["versions"] == 0


def test_upgrade_rejects_normalized_base_collision_without_writes():
    db = mongomock.MongoClient().synthetic
    for subpanel in (None, "base"):
        rule = legacy_rule()
        rule["scope"].update(asp_id="panel", subpanel_id=subpanel)
        db.query_rule_sets.insert_one(rule)
    with pytest.raises(ValueError, match="collision"):
        migration.upgrade(db, actor="tester")
    assert db.query_rule_revisions.count_documents({}) == 0
