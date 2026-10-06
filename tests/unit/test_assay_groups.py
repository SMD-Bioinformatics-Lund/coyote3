"""Assay group installation, protection, dynamic choices and validation."""

from types import SimpleNamespace

import mongomock
import pytest
from pydantic import ValidationError

from api.application.resources.asp import AspService
from api.application.resources.assay_groups import AssayGroupService
from api.contracts.schemas.assay_groups import AssayGroupCreate, AssayGroupStatus
from api.domain.core.exceptions import AppError
from api.infra.mongo.index_management import build_index_plan
from api.infra.mongo.repositories.assay_groups import AssayGroupRepository
from api.infra.mongo.repositories.assay_panels import ASPRepository
from scripts.bootstrap.install_assay_groups import install
from tests.unit.test_mongo_index_management import adapter_for


@pytest.fixture
def registry(monkeypatch):
    """Use synthetic storage with transaction callbacks executed synchronously."""
    monkeypatch.setattr(
        "api.infra.mongo.repositories.assay_groups.enqueue_audit", lambda *_a, **_k: None
    )
    monkeypatch.setattr(
        "api.infra.mongo.repositories.assay_groups.run_transaction",
        lambda _, callback: callback(None),
    )
    monkeypatch.setattr(
        "scripts.bootstrap.install_assay_groups.run_transaction", lambda _, callback: callback(None)
    )
    db = mongomock.MongoClient().test
    adapter = SimpleNamespace(
        assay_groups_collection=db.assay_groups, asp_collection=db.assay_specific_panels
    )
    repository = AssayGroupRepository(adapter)
    repository.ensure_indexes()
    return db, repository, ASPRepository(adapter)


def test_installation_is_explicit_idempotent_and_preserves_custom_groups(registry):
    db, repository, panels = registry
    db.assay_specific_panels.insert_one({"asp_id": "demo", "asp_group": "custom-scope"})
    assert install(db, actor="operator") == 10
    assert repository.list() == []
    assert install(db, actor="operator", apply=True) == 10
    before = repository.list()
    assert install(db, actor="other", apply=True) == 0
    assert repository.list() == before
    assert db.assay_groups.find_one({"group_id": "solid"})["system_managed"] is True
    assert db.assay_groups.find_one({"group_id": "demo"})["system_managed"] is True
    assert db.assay_groups.find_one({"group_id": "custom-scope"})["system_managed"] is False
    assert "custom-scope" in panels.group_options()
    assert db.assay_specific_panels.find_one()["asp_group"] == "custom-scope"


def test_create_custom_group_and_select_in_assay_form(registry):
    db, repository, panels = registry
    service = AssayGroupService(repository)
    result = service.create(
        AssayGroupCreate(group_id="methylation", display_name="Methylation"), actor="author"
    )
    assert result["resource_id"] == "methylation"
    record = db.assay_groups.find_one({"group_id": "methylation"})
    assert record["system_managed"] is False
    assert record["created_by"] == "author"
    assert record["_id"] is not None
    form = AspService(assay_panel_repository=panels).create_context_payload(actor_username="author")
    assert form["form"]["fields"]["asp_group"]["options"] == ["methylation"]
    with pytest.raises(AppError) as error:
        service.create(
            AssayGroupCreate(group_id="methylation", display_name="Changed"), actor="author"
        )
    assert error.value.status_code == 409
    assert db.assay_groups.find_one()["display_name"] == "Methylation"


def test_system_group_cannot_be_replaced_by_creation(registry):
    db, repository, _ = registry
    install(db, actor="operator", apply=True)
    with pytest.raises(AppError):
        AssayGroupService(repository).create(
            AssayGroupCreate(group_id="solid", display_name="Changed"), actor="author"
        )
    assert db.assay_groups.find_one({"group_id": "solid"})["display_name"] == "Solid tumors"


@pytest.mark.parametrize(
    "values",
    [
        {"group_id": "two words", "display_name": "Test"},
        {"group_id": "valid", "display_name": "   "},
        {"group_id": "valid", "display_name": "Test", "system_managed": True},
        {"group_id": "valid", "display_name": "Test", "created_by": "another"},
    ],
)
def test_invalid_or_spoofed_metadata_is_rejected(values):
    with pytest.raises(ValidationError):
        AssayGroupCreate.model_validate(values)


def test_index_contract_accepts_registry_declaration(registry):
    _, repository, _ = registry
    plan = build_index_plan(adapter_for(repository))
    assert plan[0]["name"] == "assay_group_id_unique"
    assert plan[0]["state"] == "present"


def test_assay_cannot_select_unregistered_scope(registry):
    _, _, panels = registry
    with pytest.raises(AppError) as error:
        AspService(assay_panel_repository=panels).create(
            payload={
                "config": {
                    "asp_id": "demo",
                    "asp_group": "not-registered",
                    "display_name": "Demo",
                    "asp_category": "dna",
                    "asp_family": "panel-dna",
                }
            }
        )
    assert error.value.status_code == 422


def test_system_group_status_changes_preserve_children_and_seed_reinstallation(registry):
    db, repository, panels = registry
    install(db, actor="operator", apply=True)
    db.assay_specific_panels.insert_many(
        [
            {"asp_id": "active", "asp_group": "demo", "is_active": True},
            {"asp_id": "inactive", "asp_group": "demo", "is_active": False},
        ]
    )
    before = list(db.assay_specific_panels.find())
    service = AssayGroupService(repository)
    assert service.impact("demo")["assays"] == ["active", "inactive"]
    result = service.change_status(
        "demo",
        AssayGroupStatus(
            is_active=False,
            expected_version=1,
            reason="Suspend new work",
        ),
        actor="admin",
    )
    assert result["meta"]["revision"]["previous_is_active"] is True
    assert "demo" not in panels.group_options()
    assert "demo" in panels.get_all_asp_groups()
    assert panels.get_asp("active")["asp_id"] == "active"
    assert list(db.assay_specific_panels.find()) == before
    install(db, actor="operator", apply=True)
    assert repository.get("demo")["is_active"] is False
    assert repository.get("demo")["system_managed"] is True
    assert repository.get("demo")["updated_by"] == "admin"
    with pytest.raises(AppError) as error:
        service.change_status(
            "demo",
            AssayGroupStatus(
                is_active=True,
                expected_version=1,
                reason="Stale request",
            ),
            actor="other",
        )
    assert error.value.status_code == 409
    service.change_status(
        "demo",
        AssayGroupStatus(
            is_active=True,
            expected_version=2,
            reason="Resume new work",
        ),
        actor="admin",
    )
    assert "demo" in panels.group_options()
    assert list(db.assay_specific_panels.find()) == before


def test_blank_status_reason_is_rejected():
    with pytest.raises(ValidationError):
        AssayGroupStatus(is_active=False, expected_version=1, reason="   ")


def test_installer_backfills_only_missing_status_fields(registry):
    db, repository, _ = registry
    db.assay_groups.insert_one({"group_id": "old-custom", "display_name": "Old custom"})
    db.assay_groups.insert_one({"group_id": "disabled-custom", "is_active": False, "version": 5})
    install(db, actor="operator", apply=True)
    assert repository.get("old-custom")["is_active"] is True
    assert repository.get("old-custom")["version"] == 1
    assert repository.get("disabled-custom")["is_active"] is False
    assert repository.get("disabled-custom")["version"] == 5
