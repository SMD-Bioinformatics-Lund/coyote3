"""Immutable clinical rule revision repository tests."""

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongomock
import pytest
from pydantic import ValidationError

from api.infra.mongo.repositories.clinical_rule_sets import (
    ClinicalRuleRevisionRepository,
    ClinicalRuleSetRepository,
    build_revision_snapshot,
    verify_revision_snapshot,
)
from scripts.backfill_clinical_rule_revisions import capture_missing_baselines
from tests.unit.reporting.test_clinical_rules import _document


def _payload() -> dict:
    return _document().model_dump(mode="python", by_alias=True, exclude_none=True)


def _adapter():
    database = mongomock.MongoClient().coyote3
    return SimpleNamespace(
        clinical_rule_sets_collection=database.clinical_rule_sets,
        clinical_rule_revisions_collection=database.clinical_rule_revisions,
    )


def test_revision_hash_is_canonical_and_content_sensitive() -> None:
    document = _payload()
    occurred_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    first = build_revision_snapshot(
        document,
        action="draft_created",
        actor="author",
        occurred_at=occurred_at,
        reason=None,
        previous_revision_hash=None,
    )
    same = build_revision_snapshot(
        deepcopy(document),
        action="draft_created",
        actor="author",
        occurred_at=occurred_at,
        reason=None,
        previous_revision_hash=None,
    )
    changed_document = deepcopy(document)
    changed_document["name"] = "Changed"
    changed = build_revision_snapshot(
        changed_document,
        action="draft_created",
        actor="author",
        occurred_at=occurred_at,
        reason=None,
        previous_revision_hash=None,
    )

    assert first["revision_hash"] == same["revision_hash"]
    assert changed["revision_hash"] != first["revision_hash"]
    assert verify_revision_snapshot(first)["revision_hash"] == first["revision_hash"]
    with pytest.raises(RuntimeError, match="integrity verification failed"):
        verify_revision_snapshot({**first, "actor": "another-author"})
    with pytest.raises(ValidationError, match="revision number must match"):
        verify_revision_snapshot({**first, "revision": 2})


def test_baseline_and_subsequent_revision_form_a_contiguous_hash_chain() -> None:
    adapter = _adapter()
    repository = ClinicalRuleSetRepository(adapter)
    first_document = _payload()
    first_document["revision"] = 4
    baseline = repository.capture_baseline(
        first_document, actor="operator", occurred_at=datetime.now(timezone.utc)
    )
    assert baseline is not None
    assert (
        repository.capture_baseline(
            first_document, actor="operator", occurred_at=datetime.now(timezone.utc)
        )
        is None
    )

    next_document = deepcopy(first_document)
    next_document["revision"] = 5
    next_document["name"] = "Edited"
    next_revision = repository._insert_revision(
        next_document,
        action="draft_updated",
        actor="author",
        reason="Updated wording",
        occurred_at=datetime.now(timezone.utc) + timedelta(seconds=1),
        session=None,
    )

    assert next_revision["previous_revision_hash"] == baseline["revision_hash"]
    with pytest.raises(RuntimeError, match="not contiguous"):
        repository._insert_revision(
            {**next_document, "revision": 7},
            action="draft_updated",
            actor="author",
            reason=None,
            occurred_at=datetime.now(timezone.utc),
            session=None,
        )


def test_revision_reader_orders_history_and_rejects_invalid_identifiers() -> None:
    adapter = _adapter()
    writer = ClinicalRuleSetRepository(adapter)
    document = _payload()
    writer.capture_baseline(document, actor="operator", occurred_at=datetime.now(timezone.utc))
    document = {**document, "revision": 2}
    writer._insert_revision(
        document,
        action="draft_updated",
        actor="author",
        reason=None,
        occurred_at=datetime.now(timezone.utc),
        session=None,
    )
    reader = ClinicalRuleRevisionRepository(adapter)
    reader.ensure_indexes()

    assert [item["revision"] for item in reader.list_for_version(document["_id"])] == [2, 1]
    assert reader.get_revision(document["_id"], 1)["revision"] == 1
    assert reader.list_for_version("invalid") == []
    assert reader.get_revision("invalid", 1) is None

    adapter.clinical_rule_revisions_collection.update_one(
        {"revision": 2}, {"$set": {"previous_revision_hash": "b" * 64}}
    )
    tampered = adapter.clinical_rule_revisions_collection.find_one({"revision": 2})
    tampered["revision_hash"] = build_revision_snapshot(
        tampered["document"],
        action=tampered["action"],
        actor=tampered["actor"],
        occurred_at=tampered["occurred_at"],
        reason=tampered.get("reason"),
        previous_revision_hash=tampered["previous_revision_hash"],
    )["revision_hash"]
    adapter.clinical_rule_revisions_collection.replace_one({"_id": tampered["_id"]}, tampered)
    with pytest.raises(RuntimeError, match="hash chain is broken"):
        reader.list_for_version(document["_id"])


def test_backfill_is_validated_idempotent_and_supports_dry_run() -> None:
    database = mongomock.MongoClient().coyote3
    document = _payload()
    document["revision"] = 3
    database.clinical_rule_sets.insert_one(document)

    assert capture_missing_baselines(database, actor="operator", dry_run=True) == (1, 0)
    assert database.clinical_rule_revisions.count_documents({}) == 0
    assert list(database.clinical_rule_revisions.list_indexes()) == []
    assert capture_missing_baselines(database, actor="operator", dry_run=False) == (1, 0)
    assert capture_missing_baselines(database, actor="operator", dry_run=False) == (0, 1)
    snapshot = database.clinical_rule_revisions.find_one({})
    assert snapshot["revision"] == 3
    assert snapshot["document"]["revision"] == 3
