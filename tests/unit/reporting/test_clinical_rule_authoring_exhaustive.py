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
    ClinicalRuleTransition,
)
from api.domain.core.exceptions import AppError
from tests.unit.reporting.test_clinical_rules import _context, _document


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

    def transition(self, _document_id, *, from_statuses, changes, event):
        if self.fail_transition or self.document["status"] not in from_statuses:
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

    def publish(self, document_id, *, changes, event):
        if self.fail_publish:
            return None
        return self.transition(
            document_id, from_statuses={"approved"}, changes=changes, event=event
        )


class RevisionRepository:
    def __init__(self, document):
        self.document = document

    def list_for_version(self, _document_id):
        return [deepcopy(self.document)]

    def get_revision(self, _document_id, revision):
        return deepcopy(self.document) if revision == self.document["revision"] else None


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
    service = ClinicalRuleAuthoringService(object(), assay_panel_repository=panels)
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
    service = ClinicalRuleAuthoringService(repository, assay_panel_repository=panels)
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


def test_submit_review_reject_and_retire_lifecycle() -> None:
    repository = Repository(_document(status="draft"))
    service = ClinicalRuleAuthoringService(repository)
    submitted = service.submit("id", ClinicalRuleTransition(reason="ready"), actor="author")
    assert submitted["status"] == "submitted"
    reviewing = service.start_review(
        "id", ClinicalRuleTransition(reason="review"), actor="reviewer"
    )
    assert reviewing["status"] == "in_clinical_review"
    rejected = service.clinical_decision(
        "id",
        ClinicalRuleDecision(approve=False, reason="needs changes"),
        actor="other-reviewer",
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

    repository = Repository(_document(status="draft"))
    repository.fail_transition = True
    with pytest.raises(AppError, match="cannot transition"):
        ClinicalRuleAuthoringService(repository).start_review(
            "id", ClinicalRuleTransition(), actor="reviewer"
        )


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
    repository = Repository(approved)
    repository.fail_publish = True
    with pytest.raises(AppError, match="Only an approved"):
        ClinicalRuleAuthoringService(repository).publish(
            "id", ClinicalRuleTransition(), actor="publisher"
        )
