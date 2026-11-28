"""Direct resource publication and rollback against an explicitly disposable replica set."""

import os
from types import SimpleNamespace
from uuid import uuid4

import pytest
from coyote.domain.exceptions import AppError
from coyote_mongo.repositories.assay_configurations import ASPConfigRepository
from coyote_mongo.repositories.gene_lists import ISGLRepository
from coyote_mongo.repositories.samples import SampleRepository
from pymongo import MongoClient

from tests.fixtures.mongo_settings import mongo_runtime


@pytest.fixture
def resources():
    uri = os.getenv("ASSAY_RESOURCE_TEST_MONGO_URI")
    if not uri or os.getenv("COYOTE4_RUN_DISPOSABLE_TESTS") != "1":
        pytest.skip("Requires a disposable replica set through the transaction test runner")
    client = MongoClient(uri, serverSelectionTimeoutMS=3000)
    db = client[f"coyote4_resource_test_{uuid4().hex}"]
    adapter = SimpleNamespace(
        app=mongo_runtime(),
        asp_collection=db.asp,
        aspc_collection=db.aspc,
        insilico_genelist_collection=db.isgl,
        assay_groups_collection=db.groups,
    )
    try:
        lists = ISGLRepository(adapter)
        lists.ensure_indexes()
        ASPConfigRepository(adapter).ensure_indexes()
        db.groups.insert_one({"group_id": "group", "is_active": True})
        for name in ("panel-a", "panel-b"):
            db.asp.insert_one(
                {
                    "asp_id": name,
                    "asp_group": "group",
                    "asp_category": "dna",
                    "asp_family": "panel-dna",
                    "version": 1,
                    "is_active": True,
                }
            )
            db.aspc.insert_one(
                {
                    "aspc_id": name,
                    "asp_id": name,
                    "diagnosis_id": "base",
                    "environment": "production",
                    "asp_group": "group",
                    "asp_category": "dna",
                    "version": 1,
                    "is_active": True,
                }
            )
        yield db, lists
    finally:
        client.drop_database(db.name)
        client.close()


def install_list(repository):
    return repository.create_genelist(
        {
            "isgl_id": "shared",
            "asp_groups": ["group"],
            "genes": ["TP53"],
            "list_type": ["snv"],
            "is_active": True,
            "adhoc": False,
            "version": 1,
        }
    )


def test_group_list_advances_each_configuration_and_preserves_pins(resources):
    db, repository = resources
    pinned = db.aspc.find_one({"asp_id": "panel-a"})["_id"]
    db.samples.insert_one({"current_aspc_id": pinned})
    install_list(repository)
    for name in ("panel-a", "panel-b"):
        active = db.aspc.find_one({"asp_id": name, "is_active": True})
        assert active["version"] == 2
        assert active["gene_list_release"]["content"]["shared"]["genes"] == ["TP53"]
        assert db.aspc.find_one({"_id": active["supersedes_id"]})["is_active"] is False
    assert db.samples.find_one()["current_aspc_id"] == pinned
    assert db.audit_outbox.count_documents({}) == 3


def test_failure_rotating_dependent_configuration_rolls_back_resource_and_audit(
    resources, monkeypatch
):
    db, repository = resources
    from coyote_mongo.repositories import revision_rotation

    def reject_receipt(*args, **kwargs):
        raise RuntimeError("synthetic receipt failure")

    monkeypatch.setattr(revision_rotation, "enqueue_audit", reject_receipt)
    with pytest.raises(RuntimeError, match="synthetic receipt failure"):
        install_list(repository)
    assert db.isgl.count_documents({}) == 0
    assert db.aspc.count_documents({"is_active": True, "version": 1}) == 2
    assert db.aspc.count_documents({}) == 2
    assert db.audit_outbox.count_documents({}) == 0


def test_only_the_reviewed_sample_moves_and_a_stale_choice_rolls_back(resources):
    db, lists = resources
    adapter = lists.adapter
    adapter.client = db.client
    adapter.samples_collection = db.samples
    adapter.assay_configuration_repository = ASPConfigRepository(adapter)
    samples = SampleRepository(adapter)
    initial = db.aspc.find_one({"asp_id": "panel-a"})
    context = {
        "asp_id": "panel-a",
        "diagnosis_id": "base",
        "environment": "production",
        "version": 1,
        "current_aspc_id": initial["_id"],
    }
    selected, other = db.samples.insert_many([dict(context), dict(context)]).inserted_ids
    install_list(lists)
    active = db.aspc.find_one({"asp_id": "panel-a", "is_active": True})
    with pytest.raises(AppError, match="active configuration changed"):
        samples.update_sample_filters(
            str(selected), {}, aspc=initial, expected_version=1, apply_latest=True
        )
    assert db.samples.find_one({"_id": selected})["version"] == 1
    receipts = db.audit_outbox.find({"event.event_type": "sample.configuration_applied"})
    assert list(receipts) == []
    samples.update_sample_filters(
        str(selected),
        {},
        aspc=active,
        expected_version=1,
        settings_reason="Reviewed expanded gene list",
        apply_latest=True,
    )
    assert db.samples.find_one({"_id": selected})["current_aspc_id"] == active["_id"]
    assert db.samples.find_one({"_id": other})["current_aspc_id"] == initial["_id"]
    receipt = db.audit_outbox.find_one({"event.event_type": "sample.configuration_applied"})
    assert receipt["event"]["metadata"]["reason"] == "Reviewed expanded gene list"
