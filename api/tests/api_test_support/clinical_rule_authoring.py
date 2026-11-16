"""Package-local synthetic records and fake ports for independent tests."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

from coyote.application.reporting.clinical_rules.authoring import ClinicalRuleAuthoringService

from api_test_support.clinical_rules import _document


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
