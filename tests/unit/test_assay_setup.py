"""Draft isolation, scope readiness, review and publication regression coverage."""

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId
from pydantic import ValidationError

from api.infra.mongo.repositories.assay_configurations import ASPConfigRepository
from api.infra.mongo.repositories.assay_diagnoses import AssayDiagnosisRepository
from api.infra.mongo.repositories.assay_setup import (
    AssaySetupRepository,
    AssaySetupRevisionRepository,
)
from coyote3.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from coyote3.application.reporting.clinical_rules.validation import content_hash
from coyote3.application.resources.assay_setup import AssaySetupService
from coyote3.config.clinical_vocabulary import CLINICAL_VOCABULARY
from coyote3.contracts.schemas.assay_setup import AssaySetupContent
from coyote3.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
from coyote3.domain.exceptions import AppError


@pytest.mark.parametrize(
    ("family", "category"), CLINICAL_VOCABULARY.assay_family_categories.items()
)
def test_setup_derives_missing_modality_from_family(family, category):
    """Managed forms can save every supported family without a readonly modality."""
    panel = dict(
        asp_id="synthetic_assay",
        asp_group="hematology",
        asp_family=family,
        display_name="Synthetic assay",
    )
    result = AssaySetupContent.model_validate({"panel": panel})
    assert result.panel.asp_category == category
    assert "asp_category" not in panel


@pytest.mark.parametrize("family, category", [("panel-dna", "rna"), ("unknown", None)])
def test_setup_rejects_conflicting_modality_and_unknown_family(family, category):
    """Deriving modality does not permit invalid or conflicting family selections."""
    panel = dict(
        asp_id="synthetic_assay",
        asp_group="hematology",
        asp_family=family,
        display_name="Synthetic assay",
    )
    if category is not None:
        panel["asp_category"] = category
    with pytest.raises(ValidationError):
        AssaySetupContent.model_validate({"panel": panel})


@pytest.fixture
def setup_service(monkeypatch):
    """Use in-memory storage; separate integration tests exercise real rollback."""
    import api.infra.mongo.repositories.assay_setup as module

    db = mongomock.MongoClient().test
    adapter = SimpleNamespace(
        client=db.client,
        assay_groups_collection=db.groups,
        assay_setups_collection=db.assay_setups,
        assay_setup_revisions_collection=db.assay_setup_revisions,
        asp_collection=db.asp,
        aspc_collection=db.aspc,
        insilico_genelist_collection=db.isgl,
        diagnoses_collection=db.diagnoses,
        diagnosis_associations_collection=db.associations,
        clinical_rule_sets_collection=db.rules,
    )
    monkeypatch.setattr(module, "run_transaction", lambda _client, callback: callback(None))
    monkeypatch.setattr(module, "enqueue_audit", lambda *_a, **_k: None)
    repository = AssaySetupRepository(adapter)
    repository.ensure_indexes()
    AssaySetupRevisionRepository(adapter).ensure_indexes()
    scopes = AssayDiagnosisRepository(adapter)
    scopes.ensure_indexes()
    store = SimpleNamespace(
        query_rule_repository=SimpleNamespace(published_for=lambda scope: []),
        configuration_profile_repository=SimpleNamespace(published=lambda: []),
        assay_setup_repository=repository,
        assay_diagnosis_repository=scopes,
        assay_panel_repository=SimpleNamespace(
            group_options=lambda: ["hematology"],
            get_asp=lambda key: db.asp.find_one({"asp_id": key}),
            get_all_asps=lambda **_: list(db.asp.find({"is_active": True})),
        ),
        gene_list_repository=SimpleNamespace(
            get_isgl_for_scope=lambda **_: list(db.isgl.find({"is_active": True})),
            get_isgl=lambda key: db.isgl.find_one({"isgl_id": key}),
        ),
        assay_configuration_repository=SimpleNamespace(
            build_aspc_id=ASPConfigRepository.build_aspc_id,
            get_aspc_with_id=lambda key: db.aspc.find_one({"aspc_id": key}),
        ),
        clinical_rule_set_repository=SimpleNamespace(
            get_active=lambda key: db.rules.find_one({"rule_set_id": key, "active": True}),
            list_active_for_assay=lambda key, **_scope: list(
                db.rules.find({"scope.asp_id": key, "active": True})
            ),
        ),
        vep_metadata_repository=SimpleNamespace(get_consequence_group_options=lambda: []),
    )
    now = datetime.now(timezone.utc)
    db.rules.insert_one(
        dict(
            rule_set_id="assay_1__base__sv",
            content_version=1,
            revision=1,
            scope=dict(asp_id="assay_1", diagnosis_id="base", analyte="dna", language="sv"),
            name="Synthetic rules",
            status="published",
            active=True,
            analysis_declarations={"SNV": {"narrative": "enabled"}},
            blocks=[],
            created_at=now,
            updated_at=now,
            published_at=now,
            created_by="author",
            updated_by="reviewer",
            published_by="publisher",
        )
    )
    doc = db.rules.find_one()
    db.rules.update_one(
        {"_id": doc["_id"]},
        {
            "$set": {
                "content_hash": content_hash(ClinicalRuleSetDoc.model_validate(doc)),
            }
        },
    )
    db.groups.insert_one({"group_id": "hematology", "is_active": True, "version": 1})
    return AssaySetupService(store, common_util=SimpleNamespace()), db


def test_review_compilation_retains_resource_hashes_across_actors(setup_service):
    service, _db = setup_service
    draft = service.save(content(), actor="author")
    author_bundle = service.bundle(draft, actor="author")
    reviewer_bundle = service.bundle(draft, actor="independent-reviewer")
    assert service.dependency_hash(author_bundle) == service.dependency_hash(reviewer_bundle)
    assert author_bundle["panel"]["created_by"] == "author"
    assert reviewer_bundle["panel"]["created_by"] == "author"
    assert author_bundle["panel"]["created_on"] == reviewer_bundle["panel"]["created_on"]


def content(**overrides):
    """Return a valid synthetic base-only setup and required report settings."""
    return AssaySetupContent.model_validate(
        {
            "panel": dict(
                asp_id="assay_1",
                asp_group="hematology",
                asp_family="panel-dna",
                asp_category="dna",
                display_name="Synthetic assay",
                expected_files=["vcf_files"],
            ),
            "environments": ["development"],
            "configurations": [
                dict(
                    diagnosis_id="base",
                    environment="development",
                    display_name="Synthetic configuration",
                    analysis_types=["SNV"],
                    filters={"somatic": {"snv": {"min_alt_reads": 5}}},
                    reporting=dict(
                        report_sections=["SNV"],
                        language="sv",
                        report_header="Header",
                        report_method="Method",
                        report_description="Description",
                        plots_path="plots",
                        report_folder="reports",
                    ),
                )
            ],
            **overrides,
        }
    )


def test_base_is_default_and_cannot_be_removed():
    assert content().scopes == ["base"]
    assert content(scopes=[]).scopes == ["base"]
    assert content(scopes=["base", "Myeloid", "myeloid"]).scopes == ["base", "myeloid"]


def test_setup_registration_rejects_repeated_separator_in_assay_id(setup_service):
    service, db = setup_service
    draft = content()
    draft.panel.asp_id = "new--assay"
    with pytest.raises(AppError, match="Invalid asp_id"):
        service.save(draft, actor="author")
    assert db.assay_setups.count_documents({}) == 0


def test_draft_isolation_and_atomic_publication_bundle(setup_service):
    service, db = setup_service
    draft = service.save(content(), actor="author")
    identifier = str(draft["_id"])
    assert db.asp.count_documents({}) == db.aspc.count_documents({}) == 0
    assert service.context(identifier, actor="author")["readiness"]["ready"]
    submitted = service.transition(identifier, 1, "submit", actor="author")
    assert db.asp.count_documents({}) == 0
    published = service.transition(identifier, submitted["revision"], "publish", actor="reviewer")
    assert published["status"] == "published"
    assert db.asp.find_one()["is_active"] is True
    assert db.aspc.find_one()["diagnosis_id"] == "base"
    assert db.associations.count_documents({}) == db.diagnoses.count_documents({}) == 0
    assert len(service.repository.revisions(identifier)) == 3
    with pytest.raises(AppError, match="current draft"):
        service.save(content(), actor="reviewer", identifier=identifier, revision=3)


def test_existing_gene_list_link_is_staged_then_versioned_at_activation(setup_service):
    """Linking preserves list content and provenance and writes only during activation."""
    service, db = setup_service
    created = datetime(2025, 1, 1, tzinfo=timezone.utc)
    original = dict(
        isgl_id="shared",
        name="Shared",
        displayname="Shared list",
        genes=["TP53"],
        list_type=["snv"],
        diagnosis=["base"],
        asp_ids=[],
        asp_groups=[],
        is_active=True,
        version=1,
        created_by="original-author",
        created_on=created,
    )
    original_id = db.isgl.insert_one(original).inserted_id
    draft = service.save(content(existing_gene_list_ids=["shared", "SHARED"]), actor="author")
    assert draft["content"]["existing_gene_list_ids"] == ["shared"]
    assert db.isgl.find_one({"_id": original_id})["asp_ids"] == []
    submitted = service.transition(str(draft["_id"]), 1, "submit", actor="author")
    assert db.isgl.count_documents({}) == 1
    service.transition(str(draft["_id"]), submitted["revision"], "publish", actor="reviewer")
    linked = db.isgl.find_one({"is_active": True})
    assert linked["asp_ids"] == ["assay_1"]
    assert linked["asp_groups"] == ["hematology"]
    assert linked["genes"] == ["TP53"]
    assert linked["created_by"] == "original-author"
    assert linked["created_on"] == created.replace(tzinfo=None)
    assert linked["updated_by"] == "reviewer"
    assert linked["version"] == 2
    assert linked["supersedes_id"] == original_id
    assert db.isgl.find_one({"_id": original_id})["is_active"] is False


@pytest.mark.parametrize(
    "changes", [{"system_installed": True}, {"is_active": False}, {"diagnosis": ["unselected"]}]
)
def test_setup_rejects_unavailable_or_protected_gene_list_links(setup_service, changes):
    """Shared lists retain ownership, activity and diagnosis restrictions."""
    service, db = setup_service
    db.isgl.insert_one(
        dict(
            isgl_id="shared",
            is_active=True,
            diagnosis=["base"],
            **{
                key: value
                for key, value in changes.items()
                if key not in {"is_active", "diagnosis"}
            },
        )
        | changes
    )
    with pytest.raises(AppError):
        service.save(content(existing_gene_list_ids=["shared"]), actor="author")
    assert db.assay_setups.count_documents({}) == 0


@pytest.mark.parametrize("action", ["publish", "return"])
def test_content_editors_cannot_approve_their_own_work(setup_service, action):
    service, _ = setup_service
    draft = service.save(content(), actor="author")
    identifier = str(draft["_id"])
    service.transition(identifier, 1, "submit", actor="author")
    with pytest.raises(AppError, match="independent reviewer"):
        service.transition(identifier, 2, action, actor="author", reason="Review")


def test_group_deactivation_blocks_pending_setup_publication(setup_service):
    service, db = setup_service
    draft = service.save(content(), actor="author")
    identifier = str(draft["_id"])
    service.transition(identifier, 1, "submit", actor="author")
    service.store.assay_panel_repository.group_options = lambda: []
    with pytest.raises(AppError, match="group"):
        service.transition(identifier, 2, "publish", actor="reviewer")
    assert db.asp.count_documents({}) == 0
    assert service.get(identifier)["status"] == "submitted"


def test_stale_edits_and_submitted_edits_are_rejected(setup_service):
    service, _ = setup_service
    draft = service.save(content(), actor="author")
    identifier = str(draft["_id"])
    service.save(content(), actor="second-editor", identifier=identifier, revision=1)
    with pytest.raises(AppError, match="current draft"):
        service.save(content(), actor="author", identifier=identifier, revision=1)
    service.transition(identifier, 2, "submit", actor="author")
    with pytest.raises(AppError, match="current draft"):
        service.save(content(), actor="author", identifier=identifier, revision=3)
    with pytest.raises(AppError, match="independent"):
        service.transition(identifier, 3, "publish", actor="second-editor")


@pytest.mark.parametrize(
    "changes, message",
    [({"environments": []}, "environment"), ({"configurations": []}, "Missing ASPCs")],
)
def test_incomplete_setup_remains_draft(setup_service, changes, message):
    service, db = setup_service
    draft = service.save(content(**changes), actor="author")
    assert not service.readiness(draft, actor="author")["ready"]
    with pytest.raises(AppError, match=message):
        service.transition(str(draft["_id"]), 1, "submit", actor="author")
    assert db.asp.count_documents({}) == 0


def test_additional_scope_requires_its_own_aspc_but_can_reuse_base_rules(setup_service):
    service, db = setup_service
    db.diagnoses.insert_one(
        dict(
            diagnosis_id="myeloid",
            display_name="Myeloid",
            description="",
            version=1,
            is_current=True,
            is_active=True,
            updated_by="author",
            updated_on=datetime.now(timezone.utc),
        )
    )
    selected = content(scopes=["myeloid"])
    draft = service.save(selected, actor="author")
    assert "myeloid/development" in service.readiness(draft, actor="author")["issues"][0]
    extra = deepcopy(selected.configurations[0])
    extra["diagnosis_id"] = "myeloid"
    selected.configurations.append(extra)
    draft = service.save(selected, actor="author", identifier=str(draft["_id"]), revision=1)
    assert service.readiness(draft, actor="author")["ready"]
    service.transition(str(draft["_id"]), 2, "submit", actor="author")
    service.transition(str(draft["_id"]), 3, "publish", actor="reviewer")
    assert db.associations.count_documents({}) == 1
    assert db.associations.find_one()["diagnosis_id"] == "myeloid"


def test_changed_rule_release_requires_resubmission(setup_service):
    service, db = setup_service
    draft = service.save(content(), actor="author")
    identifier = str(draft["_id"])
    service.transition(identifier, 1, "submit", actor="author")
    db.rules.update_one({}, {"$inc": {"revision": 1}})
    with pytest.raises(AppError, match="dependencies changed"):
        service.transition(identifier, 2, "publish", actor="reviewer")
    returned = service.transition(
        identifier, 2, "return", actor="reviewer", reason="Review updated rules"
    )
    assert returned["status"] == "draft"
    assert db.asp.count_documents({}) == 0


def test_duplicate_configurations_block_setup_but_missing_rules_only_warn(setup_service):
    service, db = setup_service
    selected = content()
    selected.configurations.append(deepcopy(selected.configurations[0]))
    draft = service.save(selected, actor="author")
    assert not service.readiness(draft, actor="author")["ready"]
    selected.configurations.pop()
    db.rules.delete_many({})
    draft = service.save(selected, actor="author", identifier=str(draft["_id"]), revision=1)
    readiness = service.readiness(draft, actor="author")
    assert readiness["ready"]
    assert readiness["issues"] == []
    assert "without an automatically generated summary" in readiness["warnings"][0]
    assert service.bundle(draft, actor="author")["rules"] == []
    identifier = str(draft["_id"])
    submitted = service.transition(identifier, draft["revision"], "submit", actor="author")
    published = service.transition(identifier, submitted["revision"], "publish", actor="reviewer")
    assert published["status"] == "published"
    assert db.aspc.count_documents({}) == 1


def test_identifier_reservation_and_unknown_scope_are_rejected(setup_service):
    service, _ = setup_service
    service.save(content(), actor="author")
    with pytest.raises(AppError, match="already exists"):
        service.save(content(), actor="other")
    with pytest.raises(AppError, match="available diagnosis"):
        service.save(content(scopes=["unknown"]), actor="author")


def test_rule_authoring_recognizes_draft_without_exposing_runtime_assay(setup_service):
    service, db = setup_service
    service.save(content(), actor="author")
    authoring = ClinicalRuleAuthoringService(
        SimpleNamespace(),
        assay_panel_repository=service.store.assay_panel_repository,
        assay_diagnosis_repository=service.store.assay_diagnosis_repository,
        assay_setup_repository=service.repository,
    )
    assert authoring.authoring_options()["assays"][0]["asp_id"] == "assay_1"
    assert db.asp.find_one() is None


def test_invalid_gene_list_can_still_be_edited(setup_service):
    service, _ = setup_service
    draft = service.save(content(gene_lists=[{"isgl_id": "invalid"}]), actor="author")
    context = service.context(str(draft["_id"]), actor="author")
    assert "genelist_form" in context
    assert "configuration_form" in context
    assert not context["readiness"]["ready"]


def test_unknown_setup_is_not_found(setup_service):
    service, _ = setup_service
    with pytest.raises(AppError, match="not found"):
        service.get(str(ObjectId()))


def test_group_deactivation_after_readiness_blocks_publication(setup_service):
    service, db = setup_service
    draft = service.save(content(), actor="author")
    bundle = service.bundle(draft, actor="reviewer")
    db.groups.update_one({}, {"$set": {"is_active": False}})
    with pytest.raises(AppError, match="group is inactive"):
        service.repository.save(
            {**draft, "revision": 2, "status": "published"},
            previous=draft,
            action="publish",
            bundle=bundle,
        )
    assert db.asp.count_documents({}) == 0
    assert service.get(str(draft["_id"]))["revision"] == 1


@pytest.mark.parametrize(
    "change, message",
    [
        ({"content_hash": "invalid"}, "integrity"),
        ({"schema_version": 999}, "schema_version"),
    ],
)
def test_setup_readiness_rejects_unusable_rule_release(setup_service, change, message):
    service, db = setup_service
    draft = service.save(content(), actor="author")
    db.rules.update_one({}, {"$set": change})
    result = service.readiness(draft, actor="author")
    assert result["ready"] is False
    assert message in result["issues"][0]
