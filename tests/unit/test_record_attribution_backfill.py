"""Attribution maintenance uses stored evidence and leaves unknown history explicit."""

import mongomock
import pytest

from scripts.maintenance.backfill_record_attribution import attribution_changes, backfill


def test_version_one_diagnosis_identifies_creator_from_first_revision_actor():
    assert attribution_changes({"version": 1, "updated_by": "first.author"}, "diagnoses") == {
        "created_by": "first.author"
    }


def test_later_revision_never_assigns_current_editor_as_creator():
    assert attribution_changes({"version": 2, "updated_by": "editor"}, "diagnoses") == {
        "created_by": None
    }


def test_system_creation_does_not_erase_recorded_human_update():
    assert attribution_changes(
        {"system_installed": True, "created_by": "installer", "updated_by": "editor"}, "asp_configs"
    ) == {"created_by": "system"}


def test_backfill_is_read_only_by_default_and_idempotent_when_applied():
    collection = mongomock.MongoClient().synthetic.diagnoses
    identity = collection.insert_one({"version": 1, "updated_by": "author"}).inserted_id
    assert backfill(collection, logical_name="diagnoses")["planned"] == 1
    assert "created_by" not in collection.find_one({"_id": identity})
    assert backfill(collection, logical_name="diagnoses", apply=True)["updated"] == 1
    assert collection.find_one({"_id": identity})["created_by"] == "author"
    assert backfill(collection, logical_name="diagnoses", apply=True)["planned"] == 0


def test_immutable_history_cannot_be_backfilled():
    with pytest.raises(ValueError, match="Immutable"):
        backfill(
            mongomock.MongoClient().synthetic.query_rule_revisions,
            logical_name="query_rule_revisions",
            apply=True,
        )


def test_later_diagnosis_recovers_creator_from_retained_first_revision():
    collection = mongomock.MongoClient().synthetic.diagnoses
    collection.insert_many(
        [
            {"diagnosis_id": "synthetic", "version": 1, "updated_by": "author"},
            {"diagnosis_id": "synthetic", "version": 2, "updated_by": "editor"},
        ]
    )
    backfill(collection, logical_name="diagnoses", apply=True)
    latest = collection.find_one({"version": 2})
    assert latest["created_by"] == "author"
    assert latest["updated_by"] == "editor"
