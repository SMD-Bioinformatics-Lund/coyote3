"""Lifecycle and failure-path tests for clinical-rule authoring."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from api.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService
from api.contracts.schemas.clinical_rules import (
    ClinicalRuleDecision,
    ClinicalRuleDraftCreate,
    ClinicalRuleDraftUpdate,
    ClinicalRuleImportRequest,
    ClinicalRuleStatus,
    ClinicalRuleTransition,
)
from api.domain.core.exceptions import AppError
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
    subpanels = SimpleNamespace(
        list_definitions=lambda: [
            {"subpanel_id": "named", "display_name": "Named", "is_active": True},
            {"subpanel_id": "unused", "display_name": "Unused", "is_active": True},
        ],
        list_for_assay=lambda *args, **kwargs: [],
    )
    service = ClinicalRuleAuthoringService(
        Repository(),
        assay_panel_repository=panels,
        assay_setup_repository=setups,
        assay_subpanel_repository=subpanels,
    )
    assert len(service._authoring_panels()) == 2
    assert [row["subpanel_id"] for row in service._registered_subpanels("assay_1")] == [
        "base",
        "named",
    ]
    assert service._registered_subpanels("unknown") == [
        {"subpanel_id": "base", "display_name": "Base"}
    ]
    service._validate_new_scope(
        ClinicalRuleDraftCreate(
            scope={"asp_id": "assay_1", "subpanel_id": "named", "analyte": "dna"},
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

    def delete_draft(self, _document_id, *, expected_revision):
        if self.document["status"] != "draft" or self.document["revision"] != expected_revision:
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
            get_all_asps=lambda **_: [{"asp_id": "assay_1", "asp_group": "demo"}],
            group_options=lambda: ["demo"],
        ),
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
    with pytest.raises(AppError, match="not a valid canonical export"):
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


def test_from_store_list_versions_get_and_audit() -> None:
    repository = Repository()
    audit = SimpleNamespace(record=lambda *args, **kwargs: setattr(audit, "call", (args, kwargs)))
    store = SimpleNamespace(
        clinical_rule_set_repository=repository,
        clinical_rule_revision_repository=SimpleNamespace(
            list_for_version=lambda _document_id: [],
            get_revision=lambda _document_id, _revision: None,
        ),
        assay_panel_repository=SimpleNamespace(get_all_asps=lambda is_active: []),
        assay_subpanel_repository=SimpleNamespace(list_for_assay=lambda *_a, **_k: []),
    )
    service = ClinicalRuleAuthoringService.from_store(store, audit_service=audit)

    result = service.list(status="published", search="assay", page=2, per_page=5)

    assert result["total"] == 1
    assert repository.list_kwargs["skip"] == 5
    assert service.versions(repository.document["rule_set_id"])
    assert service.get("id")["rule_set_id"] == repository.document["rule_set_id"]
    assert service.revisions("id") == []
    with pytest.raises(AppError, match="revision was not found"):
        service.revision("id", 1)
    service._audit("viewed", _document(status="published", active=True), "actor")
    assert audit.call[0] == ("clinical_rules.viewed", "Clinical rule set viewed")
    assert audit.call[1]["metadata"]["status"] == "published"
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
        assay_subpanel_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [{"subpanel_id": "base", "display_name": "Base"}]
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
        assay_subpanel_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [{"subpanel_id": "base", "display_name": "Base"}]
        ),
    )
    result = service.create_draft(
        ClinicalRuleDraftCreate(
            scope={"asp_id": "assay_1", "subpanel_id": "base", "analyte": "dna"},
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
        assay_subpanel_repository=SimpleNamespace(
            list_for_assay=lambda *_a, **_k: [{"subpanel_id": "base", "display_name": "Base"}]
        ),
    ).import_draft(
        ClinicalRuleImportRequest(
            document=source,
            scope={"asp_id": "assay_1", "subpanel_id": "base", "analyte": "dna"},
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


def test_validate_preview_and_update_audit_paths() -> None:
    repository = Repository(_document(status="draft"))
    audit = SimpleNamespace(record=lambda *args, **kwargs: setattr(audit, "called", True))
    service = ClinicalRuleAuthoringService(repository, audit_service=audit)
    assert service.validate("id")["valid"] is True
    preview = service.preview("id", _context().model_dump(mode="python"))
    assert preview["sections"]["Findings"] == ["Finding in TP53."]
    updated = service.update_draft(
        "id", ClinicalRuleDraftUpdate(revision=1, change_summary="Changed"), actor="author-2"
    )
    assert updated["revision"] == 2
    assert repository.update_actor == "author-2"
    assert audit.called is True


def test_only_editable_drafts_can_be_deleted_and_the_action_is_audited() -> None:
    repository = Repository(_document(status="draft"))
    audit = SimpleNamespace(record=lambda *args, **kwargs: setattr(audit, "call", (args, kwargs)))
    service = ClinicalRuleAuthoringService(repository, audit_service=audit)

    service.delete_draft("id", expected_revision=1, actor="author")

    assert repository.deleted_document["status"] == "draft"
    assert audit.call[0] == ("clinical_rules.draft_deleted", "Clinical rule set draft_deleted")

    with pytest.raises(AppError, match="Only a draft"):
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
