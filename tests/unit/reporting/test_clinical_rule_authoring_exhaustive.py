"""Lifecycle and failure-path tests for clinical-rule authoring."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from coyote3.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from coyote3.contracts.schemas.clinical_rules import (
    ClinicalRuleConfiguration,
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleDraftUpdate,
    ClinicalRuleImportRequest,
    ClinicalRuleStatus,
    ClinicalRuleTransition,
)
from coyote3.domain.exceptions import AppError
from tests.unit.reporting.test_clinical_rules import _context, _document


def test_reserved_setup_scopes_validate_new_rules_and_ignore_existing_assays():
    panel = {"asp_id": "assay_1", "asp_category": "dna", "asp_group": "demo"}
    existing = {"asp_id": "existing", "asp_category": "dna", "asp_group": "demo"}
    panels = SimpleNamespace(
        get_all_asps=lambda **_: [existing],
        get_asp=lambda identity: existing if identity == "existing" else None,
        group_options=lambda: ["demo"],
    )
    setups = SimpleNamespace(
        authoring_scopes=lambda: [
            {"content": {"panel": existing, "scopes": ["base"]}},
            {"content": {"panel": panel, "scopes": ["base", "named"]}},
        ]
    )
    diagnoses = SimpleNamespace(
        list_definitions=lambda: [
            {"diagnosis_id": "named", "display_name": "Named", "is_active": True},
            {"diagnosis_id": "unused", "display_name": "Unused", "is_active": True},
        ],
        list_for_assay=lambda *args, **kwargs: [],
    )
    service = ClinicalRuleAuthoringService(
        Repository(),
        assay_panel_repository=panels,
        assay_setup_repository=setups,
        assay_diagnosis_repository=diagnoses,
    )
    assert len(service._authoring_panels()) == 2
    assert [row["diagnosis_id"] for row in service._registered_diagnoses("assay_1")] == [
        "base",
        "named",
    ]
    assert service._registered_diagnoses("unknown") == [
        {"diagnosis_id": "base", "display_name": "Base"}
    ]
    service._validate_new_scope(
        ClinicalRuleDraftCreate(
            scope={"asp_id": "assay_1", "diagnosis_id": "named", "analyte": "dna"},
            name="New rule",
        )
    )


def test_metadata_edit_preserves_schema_version():
    document = _document(status="draft", active=False)
    blocks = document.model_dump(mode="python")["blocks"]
    blocks[0]["section"] = "clinical_question"
    blocks[0]["analysis"] = None
    service = ClinicalRuleAuthoringService(Repository(document))
    updated = service.update_draft(
        "id",
        ClinicalRuleDraftUpdate(revision=document.revision, blocks=blocks),
        actor="author",
    )
    assert updated["schema_version"] == 1


def test_missing_assay_allows_new_and_imported_drafts_but_not_submission():
    """A planned assay can be authored before registration without entering review."""
    repository = Repository()
    service = ClinicalRuleAuthoringService(
        repository, assay_panel_repository=SimpleNamespace(get_asp=lambda _identity: None)
    )
    source = _document(status="draft")
    created = service.create_draft(
        ClinicalRuleDraftCreate(scope=source.scope, name="Planned assay rules"), actor="author"
    )
    assert created["status"] == "draft"
    imported = service.import_draft(
        ClinicalRuleImportRequest(
            document=source.model_dump(mode="python", by_alias=True),
            scope=source.scope,
            name="Imported planned assay",
        ),
        actor="author",
    )
    assert imported["scope"]["asp_id"] == "assay_1"
    edited = service.update_draft(
        "id", ClinicalRuleDraftUpdate(revision=1, name="Edited before registration"), actor="author"
    )
    assert edited["name"] == "Edited before registration"
    with pytest.raises(AppError, match="active assay panel"):
        service.submit("id", ClinicalRuleTransition(assignee="reviewer"), actor="author")


def test_link_draft_updates_identity_and_version_without_changing_document_id_or_content():
    """Reassociation preserves authored rules, ownership and the audited document identity."""
    document = _document(status="draft")
    repository = Repository(document)
    service = governed_service(repository)
    result = service.update_draft(
        "id",
        ClinicalRuleDraftUpdate(
            revision=1,
            scope={
                "asp_id": "registered_assay",
                "diagnosis_id": "base",
                "analyte": "dna",
                "language": "sv",
            },
        ),
        actor="author",
    )
    assert result["_id"] == document.id_
    assert result["created_by"] == document.created_by
    assert result["rule_set_id"] == "registered_assay__base__sv"
    assert result["content_version"] == 2
    assert result["revision"] == 2
    assert result["blocks"] == document.model_dump(mode="python")["blocks"]
    assert result["test_cases"] == document.model_dump(mode="python")["test_cases"]
    with pytest.raises(AppError, match="changed while"):
        service.update_draft(
            "id", ClinicalRuleDraftUpdate(revision=1, scope=document.scope), actor="author"
        )


@pytest.mark.parametrize("state", ["submitted", "approved", "published"])
def test_reassociation_rejects_non_drafts(state):
    """Reviewed and released scope identities cannot be changed through draft updates."""
    service = governed_service(Repository(_document(status=state, active=state == "published")))
    with pytest.raises(AppError, match="Only a draft"):
        service.update_draft(
            "id", ClinicalRuleDraftUpdate(revision=1, scope=_document().scope), actor="author"
        )


def test_reconfirming_draft_scope_keeps_its_content_version():
    """Saving the current association must not allocate a new content lineage."""
    document = _document(status="draft")
    repository = Repository(document)
    repository.next_content_version = Mock(side_effect=AssertionError("Unexpected new lineage"))
    updated = governed_service(repository).update_draft(
        "id", ClinicalRuleDraftUpdate(revision=1, scope=document.scope), actor="author"
    )
    assert updated["content_version"] == document.content_version
    assert updated["revision"] == 2


def test_review_start_rejects_a_version_removed_during_transition():
    """A disappearance between validation and transition must not create a review event."""
    repository = Repository(_document(status="submitted"))
    repository.document["review"] = {"clinical_reviewer": "reviewer"}
    repository.get = Mock(side_effect=[deepcopy(repository.document), None])
    with pytest.raises(AppError) as failure:
        governed_service(repository).start_review("id", ClinicalRuleTransition(), actor="reviewer")
    assert failure.value.status_code == 404
    assert repository.document["status"] == "submitted"


@pytest.mark.parametrize("failure", ["missing", "inactive", "analyte", "diagnosis"])
def test_link_draft_requires_a_registered_compatible_assay_and_diagnosis(failure):
    """Deferred creation does not relax explicit linking checks."""
    service = governed_service(Repository(_document(status="draft")))
    panel = {
        "asp_id": "assay_1",
        "asp_category": "rna" if failure == "analyte" else "dna",
        "is_active": failure != "inactive",
    }
    service.assay_panel_repository.get_asp = lambda _identity: (
        None if failure == "missing" else panel
    )
    scope = _document().scope.model_dump()
    if failure == "diagnosis":
        scope["diagnosis_id"] = "unassociated"
    with pytest.raises(AppError):
        service.update_draft("id", ClinicalRuleDraftUpdate(revision=1, scope=scope), actor="author")


def test_conflict_group_edit_preserves_schema_version():
    document = _document(status="draft", active=False)
    blocks = document.model_dump(mode="python")["blocks"]
    blocks[0]["conflict_group"] = "classification"
    blocks[0]["match_strategy"] = "at_most_one"
    service = ClinicalRuleAuthoringService(Repository(document))
    updated = service.update_draft(
        "id",
        ClinicalRuleDraftUpdate(revision=document.revision, blocks=blocks),
        actor="author",
    )
    assert updated["schema_version"] == 1
    assert updated["blocks"][0]["conflict_group"] == "classification"


def test_publish_rejects_an_assay_no_longer_available():
    document = _document(status="approved", active=False)
    document.review.clinical_reviewer = "reviewer"
    document.review.publisher = "publisher"
    service = governed_service(Repository(document))
    service.assay_panel_repository.get_all_asps = lambda **_: []
    with pytest.raises(AppError, match="Assay is unavailable"):
        service.publish("id", ClinicalRuleTransition(), actor="publisher")


@pytest.mark.parametrize("operation,status", [("submit", "draft"), ("publish", "approved")])
def test_review_gates_require_embedded_tests(operation, status):
    document = _document(status=status, active=False)
    document.test_cases = []
    service = governed_service(Repository(document))
    readiness = service.validate("id")
    assert readiness["valid"] is False
    assert "No embedded clinical rule test cases are configured" in readiness["errors"]
    with pytest.raises(AppError) as failure:
        getattr(service, operation)(
            "id", ClinicalRuleTransition(assignee="reviewer"), actor="author"
        )
    assert failure.value.status_code == 422
    assert service.repository.document["status"] == status


def test_submit_rejects_edit_after_validation(monkeypatch):
    service = governed_service(Repository(_document(status="draft", active=False)))

    def assign(*args, **kwargs):
        service.repository.document["revision"] += 1
        service.repository.document["blocks"][0]["rules"][0]["output"] = []
        return "reviewer"

    monkeypatch.setattr(service, "_validate_assignee", assign)
    with pytest.raises(AppError) as failure:
        service.submit("id", ClinicalRuleTransition(assignee="reviewer"), actor="author")
    assert failure.value.status_code == 409
    assert service.repository.document["status"] == "draft"


class Repository:
    def __init__(self, document=None):
        self.document = (document or _document(status="published", active=True)).model_dump(
            mode="python", by_alias=True
        )
        self.fail_transition = False
        self.fail_publish = False

    def get(self, document_id):
        if document_id == "missing":
            return None
        return deepcopy(self.document)

    def list_rule_sets(self, **kwargs):
        self.list_kwargs = kwargs
        return [deepcopy(self.document)], 1

    def list_versions(self, rule_set_id):
        return [deepcopy(self.document)] if rule_set_id == self.document["rule_set_id"] else []

    def next_content_version(self, _rule_set_id):
        return 2

    def insert(self, document, *, action, actor, reason=None):
        self.insert_metadata = (action, actor, reason)
        self.document = deepcopy(document)
        return deepcopy(self.document)

    def update_draft(self, _document_id, *, expected_revision, changes, actor):
        self.update_actor = actor
        if self.document["revision"] != expected_revision:
            return None
        self.document.update(changes)
        self.document["revision"] += 1
        return deepcopy(self.document)

    def delete_draft(self, _document_id, *, expected_revision, actor):
        self.delete_actor = actor
        if (
            self.document["status"] in {"published", "retired"}
            or self.document["revision"] != expected_revision
        ):
            return None
        deleted = deepcopy(self.document)
        self.deleted_document = deleted
        return deleted

    def transition(self, _document_id, *, expected_revision, from_statuses, changes, event):
        if (
            self.fail_transition
            or self.document["status"] not in from_statuses
            or self.document["revision"] != expected_revision
        ):
            return None
        for key, value in changes.items():
            if "." in key:
                parent, child = key.split(".", 1)
                self.document.setdefault(parent, {})[child] = value
            else:
                self.document[key] = value
        self.document["revision"] += 1
        self.document.setdefault("lifecycle", []).append(event)
        return deepcopy(self.document)

    def publish(self, document_id, *, expected_revision, changes, event):
        if self.fail_publish:
            return None
        return self.transition(
            document_id,
            expected_revision=expected_revision,
            from_statuses={"approved"},
            changes=changes,
            event=event,
        )


class RevisionRepository:
    def __init__(self, document):
        self.document = document

    def list_for_version(self, _document_id):
        return [deepcopy(self.document)]

    def get_revision(self, _document_id, revision):
        return deepcopy(self.document) if revision == self.document["revision"] else None


class RoleRepository:
    def get_all_roles_plus_permissions(self):
        return [
            {
                "role_id": "clinical_rule_reviewer",
                "permissions": ["clinical_rules:clinical_review"],
            },
            {"role_id": "clinical_rule_publisher", "permissions": ["clinical_rules:publish"]},
        ]


class UserRepository:
    def list_active_users_for_notifications(self, *, role_ids):
        users = {
            "clinical_rule_reviewer": {"username": "reviewer", "fullname": "Reviewer"},
            "clinical_rule_publisher": {"username": "publisher", "fullname": "Publisher"},
        }
        return [users[role_id] for role_id in role_ids if role_id in users]


def governed_service(repository):
    return ClinicalRuleAuthoringService(
        repository,
        user_repository=UserRepository(),
        role_repository=RoleRepository(),
        assay_panel_repository=SimpleNamespace(
            get_all_asps=lambda **_: [
                {"asp_id": "assay_1", "asp_group": "demo", "asp_category": "dna"}
            ],
            get_asp=lambda identity: {
                "asp_id": identity,
                "asp_group": "demo",
                "asp_category": "dna",
                "is_active": True,
            },
            group_options=lambda: ["demo"],
        ),
        assay_diagnosis_repository=SimpleNamespace(list_for_assay=lambda *_a, **_k: []),
    )


def test_assignee_validation_rejects_missing_ineligible_and_self_review():
    service = governed_service(Repository())
    assert service._eligible_users("unassigned:permission") == []
    for username, message, exclude in [
        (None, "Assign an eligible", None),
        ("unknown", "not an active", None),
        ("reviewer", "latest content editor", "reviewer"),
    ]:
        with pytest.raises(AppError, match=message):
            service._validate_assignee(
                username, "clinical_rules:clinical_review", label="reviewer", exclude=exclude
            )


def test_import_rejects_invalid_canonical_document():
    service = governed_service(Repository())
    payload = ClinicalRuleImportRequest(
        document={}, scope=_document().scope, name="Synthetic import"
    )
    with pytest.raises(AppError, match="not a valid configuration"):
        service.import_draft(payload, actor="author")


def test_draft_delete_rejects_stale_revision():
    with pytest.raises(AppError, match="changed while it was being deleted"):
        governed_service(Repository(_document(status="draft"))).delete_draft(
            "id", expected_revision=99, actor="author"
        )


def test_assigned_review_and_publication_cannot_be_taken_by_another_user():
    document = _document(status="submitted")
    document.review.clinical_reviewer = "reviewer"
    service = governed_service(Repository(document))
    with pytest.raises(AppError, match="assigned to another"):
        service.start_review("id", ClinicalRuleTransition(), actor="other")
    with pytest.raises(AppError, match="assigned to another"):
        service.clinical_decision(
            "id", ClinicalRuleDecision(approve=False, reason="reject"), actor="other"
        )
    document.status = ClinicalRuleStatus.APPROVED
    document.review.publisher = "publisher"
    with pytest.raises(AppError, match="assigned to another"):
        governed_service(Repository(document)).publish(
            "id", ClinicalRuleTransition(), actor="other"
        )


def test_notifications_include_review_rejection_and_creator_publication():
    document = _document(status="draft")
    document.created_by = "publisher"
    repository = Repository(document)
    service = governed_service(repository)
    calls = []
    service.notification_service = SimpleNamespace(
        create_notification=lambda **kwargs: calls.append(kwargs)
    )
    service.submit("id", ClinicalRuleTransition(assignee="reviewer"), actor="author")
    service.start_review("id", ClinicalRuleTransition(), actor="reviewer")
    service.clinical_decision(
        "id",
        ClinicalRuleDecision(approve=True, publisher="publisher", reason="approved"),
        actor="reviewer",
    )
    assert (
        service.publish("id", ClinicalRuleTransition(), actor="publisher")["status"] == "published"
    )
    assert len(calls) == 2


def test_from_store_list_versions_and_get() -> None:
    repository = Repository()
    store = SimpleNamespace(
        clinical_rule_set_repository=repository,
        clinical_rule_revision_repository=SimpleNamespace(
            list_for_version=lambda _document_id: [],
            get_revision=lambda _document_id, _revision: None,
        ),
        assay_panel_repository=SimpleNamespace(get_all_asps=lambda is_active: []),
        assay_diagnosis_repository=SimpleNamespace(list_for_assay=lambda *_a, **_k: []),
        roles_repository=RoleRepository(),
        user_repository=UserRepository(),
    )
    service = ClinicalRuleAuthoringService.from_store(store)
    assert service.reviewer_options() == {
        "clinical_reviewers": [{"username": "reviewer", "name": "Reviewer"}],
        "publishers": [{"username": "publisher", "name": "Publisher"}],
    }

    result = service.list(status="published", search="assay", page=2, per_page=5)

    assert result["total"] == 1
    assert repository.list_kwargs["skip"] == 5
    assert service.versions(repository.document["rule_set_id"])
    assert service.get("id")["rule_set_id"] == repository.document["rule_set_id"]
    assert service.revisions("id") == []
    with pytest.raises(AppError, match="revision was not found"):
        service.revision("id", 1)
    with pytest.raises(AppError, match="was not found"):
        service.get("missing")


def test_authoring_options_use_identifier_as_missing_display_name() -> None:
    panels = SimpleNamespace(
        get_all_asps=lambda is_active: [
            {"asp_id": "assay_1", "asp_category": "DNA", "display_name": ""}
        ]
    )
    service = ClinicalRuleAuthoringService(
        Repository(),
        assay_panel_repository=panels,
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [{"diagnosis_id": "base", "display_name": "Base"}]
        ),
    )
    assert service.authoring_options()["assays"][0]["display_name"] == "assay_1"
    service._validate_new_scope(ClinicalRuleDraftCreate())


def test_revision_history_returns_preserved_snapshots() -> None:
    repository = Repository()
    snapshot = {"revision": 1, "document": deepcopy(repository.document)}
    service = ClinicalRuleAuthoringService(
        repository, revision_repository=RevisionRepository(snapshot)
    )

    assert service.revisions("id") == [snapshot]
    assert service.revision("id", 1) == snapshot
    with pytest.raises(AppError, match="revision was not found"):
        service.revision("id", 2)

    assert ClinicalRuleAuthoringService(repository).revisions("id") == []


def test_new_draft_creation_validates_assay_and_persists_scope() -> None:
    repository = Repository()
    panels = SimpleNamespace(
        get_asp=lambda _asp_id: {
            "asp_id": "assay_1",
            "asp_category": "DNA",
            "is_active": True,
        }
    )
    service = ClinicalRuleAuthoringService(
        repository,
        assay_panel_repository=panels,
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [{"diagnosis_id": "base", "display_name": "Base"}]
        ),
    )
    result = service.create_draft(
        ClinicalRuleDraftCreate(
            scope={"asp_id": "assay_1", "diagnosis_id": "base", "analyte": "dna"},
            name="New rules",
        ),
        actor="author",
    )
    assert result["status"] == "draft"
    assert result["content_version"] == 2
    assert result["rule_set_id"] == "assay_1__base__sv"
    assert result["lifecycle"][0]["action"] == "draft_created"
    assert result["blocks"][0]["block_id"] == "report_section_1"
    assert result["blocks"][0]["match_strategy"] == "at_most_one"
    assert result["blocks"][0]["rules"][0]["enabled"] is False
    assert repository.insert_metadata[:2] == ("draft_created", "author")


@pytest.mark.parametrize("source_status", ["published", "rejected"])
def test_clone_allowed_source_creates_clean_next_version(source_status) -> None:
    repository = Repository(_document(status=source_status, active=source_status == "published"))
    service = ClinicalRuleAuthoringService(repository)

    result = service.create_draft(
        ClinicalRuleDraftCreate(source_version_id="source"), actor="next-author"
    )

    assert result["status"] == "draft"
    assert result["active"] is False
    assert result["content_version"] == 2
    assert not any(result["review"].values())
    assert result["published_at"] is None
    assert result["content_hash"] is None


def test_clone_rejects_nonreleased_source() -> None:
    repository = Repository(_document(status="draft"))
    with pytest.raises(AppError, match="only from a published or rejected"):
        ClinicalRuleAuthoringService(repository).create_draft(
            ClinicalRuleDraftCreate(source_version_id="source"), actor="author"
        )


def test_import_creates_a_new_draft_with_canonical_provenance() -> None:
    source = _document(status="published", active=True).model_dump(mode="python", by_alias=True)
    source["blocks"][0]["conflict_group"] = "classification"
    source["blocks"][0]["match_strategy"] = "at_most_one"
    repository = Repository()
    panels = SimpleNamespace(
        get_asp=lambda _asp_id: {"asp_id": "assay_1", "asp_category": "DNA", "is_active": True}
    )
    result = ClinicalRuleAuthoringService(
        repository,
        assay_panel_repository=panels,
        assay_diagnosis_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [{"diagnosis_id": "base", "display_name": "Base"}]
        ),
    ).import_draft(
        ClinicalRuleImportRequest(
            document=source,
            scope={"asp_id": "assay_1", "diagnosis_id": "base", "analyte": "dna"},
            name="Imported report rules",
        ),
        actor="author",
    )

    assert result["status"] == "draft"
    assert result["active"] is False
    assert result["provenance"]["source"] == "import"
    assert result["lifecycle"][0]["action"] == "draft_imported"
    assert result["blocks"][0]["conflict_group"] == "classification"
    assert result["blocks"][0]["match_strategy"] == "at_most_one"
    assert result["test_cases"] == source["test_cases"]
    assert result["provenance"]["source_content_version"] == source["content_version"]
    assert result["provenance"]["source_revision"] == source["revision"]


@pytest.mark.parametrize("include_metadata", [False, True])
def test_export_import_round_trip_assigns_new_application_metadata(include_metadata):
    """Both export forms preserve authored content while import allocates a fresh draft."""
    source = _document(status="published", active=True)
    repository = Repository(source)
    service = ClinicalRuleAuthoringService(repository)
    exported = service.export("source", include_metadata=include_metadata)
    content_fields = set(ClinicalRuleConfiguration.model_fields)
    assert set(exported) == (
        set(source.model_dump(by_alias=True)) if include_metadata else content_fields
    )
    if not include_metadata:
        assert not {
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "content_version",
            "revision",
            "rule_set_id",
            "status",
            "review",
            "lifecycle",
            "_id",
        } & set(exported)
    result = service.import_draft(
        ClinicalRuleImportRequest(
            document=exported,
            scope=source.scope,
            name="Imported configuration",
        ),
        actor="new.author",
    )
    assert result["created_by"] == result["updated_by"] == "new.author"
    assert result["created_at"] == result["updated_at"]
    assert result["created_at"] >= source.created_at
    assert result["content_version"] == 2 and result["revision"] == 1
    assert result["status"] == "draft" and result["active"] is False
    assert result["published_at"] is None and result["content_hash"] is None
    assert not any(result["review"].values())
    assert result.get("_id") != source.id_
    assert result["blocks"] == source.model_dump()["blocks"]


def test_handwritten_configuration_needs_no_audit_or_version_fields():
    """The minimal file is authored content; schema_version defaults automatically."""
    source = _document()
    source_fields = source.model_dump(
        mode="json", include=set(ClinicalRuleConfiguration.model_fields)
    )
    source_fields.pop("schema_version")
    source_fields.update(
        created_by="forged",
        updated_at="not a timestamp",
        content_version=900,
        revision=-1,
        status="published",
        active=True,
        _id="invalid id",
    )
    result = ClinicalRuleAuthoringService(Repository()).import_draft(
        ClinicalRuleImportRequest(document=source_fields, scope=source.scope, name="Imported"),
        actor="actual.author",
    )
    assert result["created_by"] == result["updated_by"] == "actual.author"
    assert result["content_version"] == 2 and result["revision"] == 1
    assert result["status"] == "draft" and result["active"] is False
    assert result["schema_version"] == 1


@pytest.mark.parametrize(
    "invalid",
    [
        {"unknown_configuration": True},
        {"schema_version": 2},
        {"blocks": "invalid"},
    ],
)
def test_portable_import_still_rejects_invalid_authored_content(invalid):
    source = _document()
    content = source.model_dump(mode="json", include=set(ClinicalRuleConfiguration.model_fields))
    content.update(invalid)
    with pytest.raises(AppError, match="not a valid configuration"):
        ClinicalRuleAuthoringService(Repository()).import_draft(
            ClinicalRuleImportRequest(document=content, scope=source.scope, name="Imported"),
            actor="author",
        )


def test_validate_preview_and_update_actor() -> None:
    repository = Repository(_document(status="draft"))
    service = ClinicalRuleAuthoringService(repository)
    assert service.validate("id")["valid"] is True
    preview = service.preview("id", _context().model_dump(mode="python"))
    assert preview["sections"]["Findings"] == ["Finding in TP53."]
    updated = service.update_draft(
        "id", ClinicalRuleDraftUpdate(revision=1, change_summary="Changed"), actor="author-2"
    )
    assert updated["revision"] == 2
    assert repository.update_actor == "author-2"


@pytest.mark.parametrize(
    "status", ["draft", "submitted", "in_clinical_review", "approved", "rejected"]
)
def test_unpublished_versions_can_be_deleted_and_the_action_is_audited(status) -> None:
    repository = Repository(_document(status=status))
    service = ClinicalRuleAuthoringService(repository)

    service.delete_draft("id", expected_revision=1, actor="author")

    assert repository.deleted_document["status"] == status
    assert repository.delete_actor == "author"

    with pytest.raises(AppError, match="Only an unpublished"):
        ClinicalRuleAuthoringService(
            Repository(_document(status="published", active=True))
        ).delete_draft("id", expected_revision=1, actor="author")


def test_submit_review_reject_and_retire_lifecycle() -> None:
    repository = Repository(_document(status="draft"))
    service = governed_service(repository)
    submitted = service.submit(
        "id", ClinicalRuleTransition(reason="ready", assignee="reviewer"), actor="author"
    )
    assert submitted["status"] == "submitted"
    reviewing = service.start_review(
        "id", ClinicalRuleTransition(reason="review"), actor="reviewer"
    )
    assert reviewing["status"] == "in_clinical_review"
    rejected = service.clinical_decision(
        "id",
        ClinicalRuleDecision(approve=False, reason="needs changes"),
        actor="reviewer",
    )
    assert rejected["status"] == "rejected"

    repository = Repository(_document(status="published", active=True))
    retired = ClinicalRuleAuthoringService(repository).retire(
        "id", ClinicalRuleTransition(reason="superseded"), actor="publisher"
    )
    assert retired["status"] == "retired"
    assert retired["active"] is False


def test_lifecycle_failure_paths(monkeypatch) -> None:
    invalid = _document(status="draft")
    invalid.blocks = []
    repository = Repository(invalid)
    service = ClinicalRuleAuthoringService(repository)
    with pytest.raises(AppError, match="validation failed"):
        service.submit("id", ClinicalRuleTransition(), actor="author")
    with pytest.raises(AppError, match="retirement reason"):
        service.retire("id", ClinicalRuleTransition(), actor="publisher")

    repository = Repository(_document(status="submitted"))
    repository.document["review"] = {"clinical_reviewer": "reviewer"}
    repository.fail_transition = True
    with pytest.raises(AppError, match="cannot transition"):
        governed_service(repository).start_review("id", ClinicalRuleTransition(), actor="reviewer")


def test_publication_rejects_invalid_unapproved_nonindependent_and_stale(monkeypatch) -> None:
    invalid = _document(status="approved")
    invalid.blocks = []
    with pytest.raises(AppError, match="validation failed"):
        ClinicalRuleAuthoringService(Repository(invalid)).publish(
            "id", ClinicalRuleTransition(), actor="publisher"
        )

    unapproved = _document(status="approved")
    unapproved.review.clinical_reviewer = None
    with pytest.raises(AppError, match="Clinical approval is required"):
        ClinicalRuleAuthoringService(Repository(unapproved)).publish(
            "id", ClinicalRuleTransition(), actor="publisher"
        )

    same_editor = _document(status="approved")
    same_editor.review.clinical_reviewer = same_editor.updated_by
    with pytest.raises(AppError, match="must be independent"):
        ClinicalRuleAuthoringService(Repository(same_editor)).publish(
            "id", ClinicalRuleTransition(), actor="publisher"
        )

    approved = _document(status="approved")
    approved.review.clinical_reviewer = "reviewer"
    approved.review.publisher = "publisher"
    repository = Repository(approved)
    repository.fail_publish = True
    with pytest.raises(AppError, match="Only an approved"):
        governed_service(repository).publish("id", ClinicalRuleTransition(), actor="publisher")
