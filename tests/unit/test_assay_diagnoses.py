"""Assay ownership, retirement, concurrency and migration regression coverage."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from pydantic import ValidationError

from api.infra.mongo.repositories.assay_diagnoses import AssayDiagnosisRepository
from api.infra.mongo.repositories.gene_lists import ISGLRepository
from coyote3.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from coyote3.application.resources.aspc import AspcService
from coyote3.application.resources.diagnoses import DiagnosisService
from coyote3.contracts.schemas.assay import InsilicoGenelistsDoc
from coyote3.contracts.schemas.clinical_rules import ClinicalRuleDraftCreate
from coyote3.contracts.schemas.diagnoses import (
    AssayDiagnosisDoc,
    DiagnosisAssociationUpdate,
    DiagnosisCreate,
    DiagnosisUpdate,
    SharedDiagnosisCreate,
    SharedDiagnosisUpdate,
)
from coyote3.domain.exceptions import AppError


@pytest.fixture
def repository(monkeypatch):
    """Use an in-memory collection; transaction rollback is tested separately."""
    import api.infra.mongo.repositories.assay_diagnoses as module

    monkeypatch.setattr(module, "run_transaction", lambda _client, callback: callback(None))
    monkeypatch.setattr(module, "enqueue_audit", lambda *_a, **_k: None)
    db = mongomock.MongoClient().test
    repo = AssayDiagnosisRepository(
        SimpleNamespace(
            diagnosis_associations_collection=db.diagnosis_associations,
            diagnoses_collection=db.diagnoses,
            aspc_collection=db.asp_configs,
        )
    )
    repo.ensure_indexes()
    return repo


@pytest.fixture
def service(repository):
    """Expose two synthetic assays with independent scope namespaces."""
    return DiagnosisService(
        panels=SimpleNamespace(
            get_asp=lambda key: (
                {"asp_id": key, "asp_group": "demo"} if key in {"panel-a", "panel-b"} else None
            ),
            group_options=lambda: ["demo"],
        ),
        diagnoses=repository,
    )


def test_scope_identity_and_history(service, repository):
    for assay in ("panel-a", "panel-b"):
        service.save(
            assay, DiagnosisCreate(diagnosis_id="myeloid", display_name="Myeloid"), actor="author"
        )
    service.save(
        "panel-a",
        DiagnosisUpdate(display_name="Myeloid", is_active=False, expected_version=1),
        diagnosis_id="myeloid",
        actor="reviewer",
    )
    assert repository.list_for_assay("panel-a", active_only=True) == []
    assert repository.get_current("panel-b", "myeloid")["is_active"] is True
    assert repository.get_current("panel-a", "myeloid")["version"] == 2
    previous = repository.get_collection().find_one({"asp_id": "panel-a", "version": 1})
    assert "display_name" not in previous
    assert repository.definitions.count_documents({"is_current": True}) == 1
    assert previous["updated_by"] == "author"
    assert previous["is_current"] is False


def test_existing_hyphenated_definition_can_be_revised(service, repository):
    repository.create_definition(
        {
            "diagnosis_id": "existing-scope",
            "display_name": "Existing scope",
            "description": "",
            "is_active": True,
            "version": 1,
            "is_current": True,
            "updated_by": "author",
            "updated_on": datetime.now(timezone.utc),
        },
        ["panel-a"],
    )
    service.revise_definition(
        "existing-scope",
        SharedDiagnosisUpdate(display_name="Updated name", expected_version=1),
        actor="editor",
    )
    row = repository.definitions.find_one({"diagnosis_id": "existing-scope", "is_current": True})
    assert row["display_name"] == "Updated name"
    assert row["version"] == 2
    assert repository.definitions.count_documents({"diagnosis_id": "existing_scope"}) == 0


def test_inactive_definition_creates_inactive_assay_links(service, repository):
    """Reactivating shared metadata must not silently activate previously disabled links."""
    service.create_definition(
        SharedDiagnosisCreate(
            diagnosis_id="shared", display_name="Shared", is_active=False, asp_ids=["panel-a"]
        ),
        actor="author",
    )
    assert repository.get_current("panel-a", "shared")["is_active"] is False
    service.revise_definition(
        "shared", SharedDiagnosisUpdate(display_name="Shared", expected_version=1), actor="editor"
    )
    assert repository.list_for_assay("panel-a", active_only=True) == []
    assert repository.get_current("panel-a", "shared")["version"] == 1


def test_shared_edit_adds_assays_without_removing_or_reactivating_links(service, repository):
    """Metadata edits preserve existing association status and add only missing links."""
    service.create_definition(
        SharedDiagnosisCreate(diagnosis_id="shared", display_name="Shared", asp_ids=["panel-a"]),
        actor="author",
    )
    service.set_association_status(
        "panel-a",
        "shared",
        DiagnosisAssociationUpdate(is_active=False, expected_version=1),
        actor="author",
    )
    service.revise_definition(
        "shared",
        SharedDiagnosisUpdate(
            display_name="Shared", expected_version=1, add_asp_ids=["panel-a", "panel-b"]
        ),
        actor="editor",
    )
    assert repository.get_current("panel-a", "shared")["is_active"] is False
    assert repository.get_current("panel-a", "shared")["version"] == 2
    assert repository.get_current("panel-b", "shared")["is_active"] is True
    service.revise_definition(
        "shared",
        SharedDiagnosisUpdate(display_name="Renamed", expected_version=2),
        actor="editor",
    )
    assert set(service.definitions_payload()["diagnoses"][0]["associated_asp_ids"]) == {
        "panel-a",
        "panel-b",
    }
    with pytest.raises(AppError):
        service.revise_definition(
            "shared",
            SharedDiagnosisUpdate(
                display_name="Invalid", expected_version=3, add_asp_ids=["missing"]
            ),
            actor="editor",
        )
    assert repository.list_definitions()[0]["version"] == 3


def test_duplicate_and_stale_edits_are_conflicts(service):
    payload = DiagnosisCreate(diagnosis_id="named", display_name="Named")
    service.save("panel-a", payload, actor="author")
    with pytest.raises(AppError) as duplicate:
        service.save("panel-a", payload, actor="author")
    assert duplicate.value.status_code == 409
    with pytest.raises(AppError) as stale:
        service.save(
            "panel-a",
            DiagnosisUpdate(display_name="Base", expected_version=3),
            diagnosis_id="named",
            actor="author",
        )
    assert stale.value.status_code == 409


def test_global_retirement_and_assay_disable_are_independent(service, repository):
    for assay in ("panel-a", "panel-b"):
        service.save(
            assay, DiagnosisCreate(diagnosis_id="shared", display_name="Shared"), actor="author"
        )
    service.save(
        "panel-a",
        DiagnosisUpdate(display_name="Shared", is_active=False, expected_version=1),
        diagnosis_id="shared",
        actor="author",
    )
    assert len(repository.list_for_assay("panel-b", active_only=True)) == 1
    result = service.revise_definition(
        "shared",
        SharedDiagnosisUpdate(display_name="Shared", is_active=False, expected_version=1),
        actor="reviewer",
    )
    assert result["meta"]["revision"] == {
        "previous_version": 1,
        "new_version": 2,
        "requested_assay_additions": [],
    }
    assert repository.list_for_assay("panel-b", active_only=True) == []
    service.revise_definition(
        "shared",
        SharedDiagnosisUpdate(display_name="Shared", is_active=True, expected_version=2),
        actor="reviewer",
    )
    assert repository.list_for_assay("panel-a", active_only=True) == []
    assert len(repository.list_for_assay("panel-b", active_only=True)) == 1


def test_shared_metadata_is_not_overwritten_through_assay_editor(service):
    service.save(
        "panel-a", DiagnosisCreate(diagnosis_id="shared", display_name="Shared"), actor="author"
    )
    with pytest.raises(AppError, match="Shared metadata differs"):
        service.save(
            "panel-b",
            DiagnosisCreate(diagnosis_id="shared", display_name="Different"),
            actor="author",
        )


def test_base_cannot_be_retired_and_unknown_assay_rejected(service):
    with pytest.raises(AppError, match="Base is implicit"):
        service.save(
            "panel-a",
            DiagnosisCreate(diagnosis_id="base", display_name="Base", is_active=False),
            actor="author",
        )
    with pytest.raises(AppError) as missing:
        service.save(
            "absent", DiagnosisCreate(diagnosis_id="test", display_name="Test"), actor="author"
        )
    assert missing.value.status_code == 404


@pytest.mark.parametrize(
    "values",
    [
        {"diagnosis_id": "bad/id", "display_name": "Test"},
        {"diagnosis_id": "test", "display_name": "   "},
        {"diagnosis_id": "test", "display_name": "Test", "asp_id": "other"},
    ],
)
def test_invalid_metadata_is_rejected(values):
    with pytest.raises(ValidationError):
        DiagnosisCreate(**values)


def test_new_aspc_requires_registry_not_gene_list():
    service = AspcService(
        assay_configuration_repository=Mock(),
        assay_panel_repository=Mock(),
        gene_list_repository=Mock(),
        vep_metadata_repository=Mock(),
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [{"diagnosis_id": "registered"}]
        ),
    )
    service._validate_diagnosis({"asp_id": "panel-a", "diagnosis_id": "registered"})
    service._validate_diagnosis({"asp_id": "panel-a", "diagnosis_id": "base"})
    with pytest.raises(AppError):
        service._validate_diagnosis({"asp_id": "panel-a", "diagnosis_id": "unregistered"})
    existing = {"asp_id": "panel-a", "diagnosis_id": "retired"}
    service._validate_diagnosis(existing, previous=existing)
    with pytest.raises(AppError):
        service._validate_diagnosis({**existing, "diagnosis_id": "registered"}, previous=existing)
    service.gene_list_repository.get_isgl_for_scope.assert_not_called()


def test_transactions_fail_closed_without_replica_set():
    db = mongomock.MongoClient().test
    repo = AssayDiagnosisRepository(
        SimpleNamespace(
            diagnosis_associations_collection=db.diagnosis_associations,
            diagnoses_collection=db.diagnoses,
        )
    )
    doc = AssayDiagnosisDoc(
        asp_id="panel-a",
        diagnosis_id="base",
        display_name="Base",
        updated_by="operator",
        updated_on=datetime.now(timezone.utc),
    )
    with pytest.raises(NotImplementedError):
        repo.save(doc.model_dump(exclude_none=True))
    assert repo.get_collection().count_documents({}) == 0


def test_clinical_rule_scopes_require_an_active_registered_diagnosis():
    """API submissions cannot bypass the assay-scoped dropdown."""
    panels = SimpleNamespace(get_asp=lambda _id: {"asp_category": "dna", "is_active": True})
    scopes = SimpleNamespace(list_for_assay=lambda *_a, **_k: [])
    service = ClinicalRuleAuthoringService(
        object(), assay_panel_repository=panels, assay_diagnosis_repository=scopes
    )
    service._validate_new_scope(
        ClinicalRuleDraftCreate(
            name="Rules", scope={"asp_id": "panel-a", "diagnosis_id": "base", "analyte": "dna"}
        )
    )
    with pytest.raises(AppError, match="active registered diagnosis"):
        service._validate_new_scope(
            ClinicalRuleDraftCreate(
                name="Rules",
                scope={"asp_id": "panel-a", "diagnosis_id": "unknown", "analyte": "dna"},
            )
        )
    with pytest.raises(RuntimeError, match="repository is required"):
        ClinicalRuleAuthoringService(object())._registered_diagnoses("panel-a")


def test_isgl_aliases_are_labels_not_scope_identifiers():
    doc = InsilicoGenelistsDoc(
        isgl_id="breast-panel",
        name="Breast panel",
        displayname="Breast cancer",
        aliases=[" BC ", "Breast Cancer Panel", "bc", ""],
        diagnosis=["breast"],
        list_type=["snv"],
    )
    assert doc.aliases == ["BC", "Breast Cancer Panel"]
    assert doc.diagnosis == ["breast"]
    with pytest.raises(ValidationError):
        InsilicoGenelistsDoc(
            isgl_id="test",
            name="Test",
            displayname="Test",
            aliases=[123],
        )


def test_isgl_alias_search_does_not_make_alias_a_lookup_key():
    collection = mongomock.MongoClient().test.insilico_genelists
    collection.insert_one(
        {
            "isgl_id": "panel-a",
            "name": "Panel",
            "displayname": "Panel A",
            "aliases": ["Alternate name"],
            "is_active": True,
        }
    )
    repository = ISGLRepository(SimpleNamespace(insilico_genelist_collection=collection))
    rows, count = repository.search_isgls(q="alternate")
    assert count == 1
    assert rows[0]["isgl_id"] == "panel-a"
    assert repository.get_isgl("alternate-name") is None


def test_create_shared_definition_with_multiple_assays(service, repository):
    payload = SharedDiagnosisCreate(
        diagnosis_id="shared", display_name="Shared", asp_ids=["panel-a", "panel-b", "panel-a"]
    )
    service.create_definition(payload, actor="author")
    assert repository.definitions.count_documents({"is_current": True}) == 1
    assert repository.get_collection().count_documents({"is_current": True}) == 2
    service.set_association_status(
        "panel-a",
        "shared",
        DiagnosisAssociationUpdate(is_active=False, expected_version=1),
        actor="author",
    )
    assert repository.get_current("panel-a", "shared")["is_active"] is False
    assert repository.get_current("panel-b", "shared")["is_active"] is True
    assert repository.definitions.find_one({"is_current": True})["version"] == 1
    with pytest.raises(AppError):
        service.set_association_status(
            "panel-a",
            "shared",
            DiagnosisAssociationUpdate(is_active=True, expected_version=1),
            actor="author",
        )


def test_shared_creation_validates_every_assay_before_writing(service, repository):
    with pytest.raises(AppError):
        service.create_definition(
            SharedDiagnosisCreate(
                diagnosis_id="shared", display_name="Shared", asp_ids=["panel-a", "missing"]
            ),
            actor="author",
        )
    assert repository.definitions.count_documents({}) == 0
    assert repository.get_collection().count_documents({}) == 0


def test_unassigned_definition_and_duplicate_rejection(service, repository):
    payload = SharedDiagnosisCreate(diagnosis_id="shared", display_name="Shared")
    service.create_definition(payload, actor="author")
    assert repository.get_collection().count_documents({}) == 0
    with pytest.raises(AppError, match="already exists"):
        service.create_definition(payload, actor="author")
    assert repository.definitions.count_documents({}) == 1
