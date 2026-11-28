"""Published dependencies move together while sample pins remain stable across library edits."""

from types import SimpleNamespace

import mongomock
import pytest
from coyote.application.common.release_resources import assay_resource, gene_list_resources
from coyote.domain.exceptions import AppError
from coyote_mongo.repositories import assay_components, revision_rotation
from coyote_mongo.repositories.assay_configurations import ASPConfigRepository
from coyote_mongo.repositories.assay_panels import ASPRepository
from coyote_mongo.repositories.gene_lists import ISGLRepository
from mongo_test_support.settings import mongo_runtime


def test_direct_edits_refresh_only_affected_configurations_and_keep_historical_membership(
    monkeypatch,
):
    db = mongomock.MongoClient().resource_library
    adapter = SimpleNamespace(
        app=mongo_runtime(),
        asp_collection=db.asp,
        aspc_collection=db.aspc,
        insilico_genelist_collection=db.isgl,
        assay_groups_collection=db.groups,
    )
    # Mongomock has no transactions. The replica-set suite covers rollback and outbox durability.
    monkeypatch.setattr(
        assay_components, "run_transaction", lambda client, operation: operation(None)
    )
    receipts = []
    for module in (assay_components, revision_rotation):
        monkeypatch.setattr(
            module, "enqueue_audit", lambda db, session, **event: receipts.append(event)
        )
    panels, lists, configs = (
        ASPRepository(adapter),
        ISGLRepository(adapter),
        ASPConfigRepository(adapter),
    )
    for group in ("shared", "independent"):
        db.groups.insert_one({"group_id": group, "is_active": True})
    for name, group in [("one", "shared"), ("two", "shared"), ("three", "independent")]:
        panels.create_panel(
            {"asp_id": name, "asp_group": group, "asp_category": "dna", "version": 1}
        )
        configs.create_assay_config(
            {
                "aspc_id": f"{name}::base::production",
                "asp_id": name,
                "asp_group": group,
                "asp_category": "dna",
                "diagnosis_id": "base",
                "environment": "production",
                "version": 1,
            }
        )
    list_row = {
        "isgl_id": "shared-genes",
        "asp_ids": [],
        "asp_groups": ["shared"],
        "list_type": ["snv"],
        "genes": ["TP53"],
        "adhoc": False,
        "version": 1,
    }
    lists.create_genelist(list_row)
    v2 = db.aspc.find_one({"asp_id": "one", "is_active": True})
    db.samples.insert_one({"current_aspc_id": v2["_id"]})
    previous = lists.get_isgl("shared-genes")
    lists.rotate_isgl(
        "shared-genes",
        {**list_row, "version": 2, "genes": ["TP53", "ATM"], "supersedes_id": previous["_id"]},
        expected_version=1,
        retire_fields={},
    )
    for name in ("one", "two"):
        active = db.aspc.find_one({"asp_id": name, "is_active": True})
        assert active["version"] == 3
        assert gene_list_resources(active)["shared-genes"]["genes"] == ["TP53", "ATM"]
    assert db.aspc.count_documents({"asp_id": "three"}) == 1
    assert lists.get_collection().count_documents({"is_active": True}) == 1
    older = configs.get_aspc_revision_no_meta(db.samples.find_one()["current_aspc_id"])
    assert older["_id"] == v2["_id"]
    assert gene_list_resources(older)["shared-genes"]["genes"] == ["TP53"]
    panel = panels.get_asp("one")
    panel_id = panel.pop("_id")
    panels.rotate_asp(
        "one",
        {**panel, "version": 2, "covered_genes": ["ATM"], "supersedes_id": panel_id},
        expected_version=1,
        retire_fields={},
    )
    assert assay_resource(db.aspc.find_one({"asp_id": "one", "is_active": True}))[
        "covered_genes"
    ] == ["ATM"]
    assert db.aspc.find_one({"asp_id": "two", "is_active": True})["version"] == 3
    assert "covered_genes" not in assay_resource(older)
    with pytest.raises(AppError, match="assay definition changed"):
        configs.create_assay_config(
            {
                "aspc_id": "one::base::testing",
                "asp_id": "one",
                "asp_category": "dna",
                "asp_group": "shared",
                "diagnosis_id": "base",
                "environment": "testing",
                "assay_resource_release": older["assay_resource_release"],
            }
        )
    assert db.aspc.count_documents({"environment": "testing"}) == 0
    assert (
        len(
            [event for event in receipts if event["event_type"] == "configuration.revision_rotated"]
        )
        == 7
    )
