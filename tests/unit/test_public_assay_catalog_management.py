"""Governance, validation, and public-data isolation for catalog authoring."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from bson import ObjectId

from api.application.resources.public_assay_catalog import PublicAssayCatalogManagementService
from api.domain.core.exceptions import AppError as ApiError


class MemoryVersions:
    def __init__(self, live):
        self.live = live
        self.documents = {}
        self.history = []

    def get(self, oid):
        return deepcopy(self.documents.get(str(oid)))

    def list(self):
        return list(self.documents.values())

    def revisions(self, oid):
        return [s for s in self.history if s["version_id"] == str(oid)]

    def insert(self, doc):
        doc = {**deepcopy(doc), "_id": ObjectId()}
        return self._store(doc)

    def _store(self, doc):
        self.documents[str(doc["_id"])] = deepcopy(doc)
        self.history.append(
            {"version_id": str(doc["_id"]), "revision": doc["revision"], "document": deepcopy(doc)}
        )
        return deepcopy(doc)

    def replace(self, previous, candidate, *, publish=False):
        current = self.get(previous["_id"])
        if current["revision"] != previous["revision"] or current["status"] != previous["status"]:
            return None
        if publish:
            release = (self.live.document or {}).get("version", 0)
            if release != previous["base_version"]:
                return None
            candidate["content_version"] = release + 1
            candidate["catalog"]["version"] = release + 1
            self.live.document = deepcopy(candidate["catalog"])
        return self._store(candidate)


@pytest.fixture
def service():
    live = SimpleNamespace(document=None)
    live.get_default = lambda: deepcopy(live.document)
    roles = [
        {"role_id": role, "permissions": [f"catalog:{permission}"]}
        for role, permission in [("reviewer", "review"), ("publisher", "publish")]
    ]
    users = SimpleNamespace(
        list_active_users_for_notifications=lambda role_ids: [
            {"username": role, "fullname": role} for role in role_ids
        ]
    )
    service = PublicAssayCatalogManagementService(
        live,
        versions=MemoryVersions(live),
        users=users,
        roles=SimpleNamespace(get_all_roles_plus_permissions=lambda: roles),
        assay_panel_repository=SimpleNamespace(get_all_asps=lambda **kw: [{"asp_id": "assay"}]),
        assay_configuration_repository=SimpleNamespace(
            get_all_aspc=lambda: [
                {
                    "asp_id": "assay",
                    "aspc_id": "assay_base",
                    "environment": "production",
                    "is_active": True,
                },
                {
                    "asp_id": "assay",
                    "aspc_id": "assay_test",
                    "environment": "test",
                    "is_active": True,
                },
            ]
        ),
        gene_list_repository=SimpleNamespace(
            get_all_isgl=lambda **kw: [{"isgl_id": "diagnosis", "genes": ["GENE1"]}]
        ),
    )
    service.notification_service = Mock()
    return service


def content():
    return {
        "header": "Synthetic catalog",
        "layout": {"order": ["wgs"]},
        "modalities": {
            "wgs": {
                "label": "Whole Genome Sequencing (WGS)",
                "categories": {
                    "solid": {
                        "label": "Solid",
                        "asp_id": "assay",
                        "aspc_id": "assay_base",
                        "tat": "7-10 days",
                        "gene_lists": [{"isgl_id": "diagnosis"}],
                    }
                },
            }
        },
    }


def draft(service):
    return service.create(actor="author", imported=content())


def approved(service):
    doc = draft(service)
    doc = service.submit(str(doc["_id"]), doc["revision"], "reviewer", actor="author")
    return service.decide(
        str(doc["_id"]),
        doc["revision"],
        actor="reviewer",
        approve=True,
        publisher="publisher",
        reason="Verified public wording",
    )


def test_full_workflow_isolates_draft_and_records_every_revision(service):
    doc = draft(service)
    oid = str(doc["_id"])
    changed = deepcopy(doc["catalog"])
    changed["header"] = "Revised public heading"
    doc = service.update(oid, 1, changed, actor="author")
    assert service.repository.get_default() is None
    doc = service.submit(oid, 2, "reviewer", actor="author")
    assert service.repository.get_default() is None
    doc = service.decide(
        oid, 3, actor="reviewer", approve=True, publisher="publisher", reason="Reviewed"
    )
    assert service.repository.get_default() is None
    doc = service.publish(oid, 4, actor="publisher")
    assert doc["content_version"] == 1
    assert service.get()["header"] == "Revised public heading"
    assert len(service.versions.revisions(oid)) == 5
    assert [e["action"] for e in doc["lifecycle"]] == [
        "imported",
        "draft_saved",
        "submitted",
        "approved",
        "published",
    ]
    calls = service.notification_service.create_notification.call_args_list
    assert [c.kwargs["recipients"] for c in calls] == [
        ["reviewer"],
        ["author"],
        ["publisher"],
        ["author"],
    ]
    assert all(c.kwargs["resource"]["uri"].endswith(oid) for c in calls)


@pytest.mark.parametrize("state", ["submitted", "approved", "rejected", "published"])
def test_only_drafts_are_editable(service, state):
    doc = draft(service)
    service.versions.documents[str(doc["_id"])]["status"] = state
    with pytest.raises(ApiError):
        service.update(str(doc["_id"]), 1, content(), actor="author")


def test_revision_conflicts_do_not_change_saved_content(service):
    doc = draft(service)
    with pytest.raises(ApiError):
        service.update(str(doc["_id"]), 99, content(), actor="author")
    assert service.document(str(doc["_id"]))["revision"] == 1


def test_every_editor_is_excluded_from_review(service):
    doc = draft(service)
    doc = service.update(str(doc["_id"]), 1, content(), actor="reviewer")
    with pytest.raises(ApiError):
        service.submit(str(doc["_id"]), 2, "reviewer", actor="author")


def test_assigned_reviewer_only_and_rejection_requires_reason(service):
    doc = draft(service)
    oid = str(doc["_id"])
    doc = service.submit(oid, 1, "reviewer", actor="author")
    for actor, reason in [("author", "No"), ("reviewer", "")]:
        with pytest.raises(ApiError):
            service.decide(oid, 2, actor=actor, approve=False, publisher="", reason=reason)
    rejected = service.decide(
        oid, 2, actor="reviewer", approve=False, publisher="", reason="Fix wording"
    )
    assert rejected["status"] == "rejected"
    assert service.repository.get_default() is None


def test_publication_increases_version_and_stale_draft_cannot_replace_it(service):
    first = approved(service)
    stale = approved(service)
    result = service.publish(str(first["_id"]), first["revision"], actor="publisher")
    assert result["content_version"] == 1
    with pytest.raises(ApiError):
        service.publish(str(stale["_id"]), stale["revision"], actor="publisher")
    next_doc = approved(service)
    assert next_doc["base_version"] == 1
    assert (
        service.publish(str(next_doc["_id"]), next_doc["revision"], actor="publisher")[
            "content_version"
        ]
        == 2
    )


def test_publication_rechecks_reviewer_eligibility(service):
    doc = approved(service)
    service.roles.get_all_roles_plus_permissions = lambda: [
        {"role_id": "publisher", "permissions": ["catalog:publish"]}
    ]
    with pytest.raises(ApiError):
        service.publish(str(doc["_id"]), doc["revision"], actor="publisher")
    assert service.repository.get_default() is None


@pytest.mark.parametrize("value", ["0 days", "10-7 days", "7.5 days", "-1 days", "seven days"])
def test_invalid_turnaround_is_rejected_before_saving(service, value):
    data = content()
    data["modalities"]["wgs"]["categories"]["solid"]["tat"] = value
    with pytest.raises(ApiError):
        service.create(actor="author", imported=data)
    assert not service.versions.documents


@pytest.mark.parametrize(
    "invalid",
    [{"modalities": {"wgs": "broken"}}, {"modalities": {"wgs": {"categories": {"x": 1}}}}],
)
def test_malformed_import_reports_validation_not_unexpected_failure(service, invalid):
    with pytest.raises(ApiError):
        service.create(actor="author", imported=invalid)


@pytest.mark.parametrize(
    "field,value",
    [
        ("aspc_id", "assay_test"),
        ("asp_id", "missing"),
        ("aspc_id", None),
        ("analysis", ["made-up-analysis"]),
    ],
)
def test_publication_requires_valid_production_references(service, field, value):
    data = content()
    data["modalities"]["wgs"]["categories"]["solid"][field] = value
    doc = service.create(actor="author", imported=data)
    with pytest.raises(ApiError):
        service.submit(str(doc["_id"]), 1, "reviewer", actor="author")


def test_duplicate_gene_lists_cannot_be_submitted(service):
    catalog = content()
    catalog["modalities"]["wgs"]["categories"]["solid"]["gene_lists"] = [
        {"isgl_id": "diagnosis"},
        {"key": "diagnosis"},
    ]
    doc = service.create(actor="author", imported=catalog)
    with pytest.raises(ApiError):
        service.submit(str(doc["_id"]), doc["revision"], "reviewer", actor="author")
    assert service.document(str(doc["_id"]))["status"] == "draft"
    service.notification_service.create_notification.assert_not_called()


def test_sources_exclude_nonproduction_and_gene_contents(service):
    options = service.source_options()
    assert [v["aspc_id"] for v in options["aspcs"]] == ["assay_base"]
    assert "genes" not in options["gene_lists"][0]


def test_import_removes_executable_html_but_keeps_public_formatting(service):
    data = content()
    data["description"] = '<p onclick="alert(1)">Public <strong>assays</strong></p>'
    entry = data["modalities"]["wgs"]["categories"]["solid"]
    entry["custom_details"] = (
        '<a href="javascript:alert(1)">Details</a><img src=x onerror=alert(1)>'
    )
    saved = service.create(actor="author", imported=data)["catalog"]
    assert saved["description"] == "<p>Public <strong>assays</strong></p>"
    assert saved["modalities"]["wgs"]["categories"]["solid"]["custom_details"] == "<a>Details</a>"


def test_identifiers_are_generated_once_and_import_never_publishes(service):
    doc = draft(service)
    oid = str(doc["_id"])
    identifier = doc["catalog"]["modalities"]["wgs"]["categories"]["solid"]["catalog_id"]
    updated = service.update(oid, 1, doc["catalog"], actor="author")
    assert (
        updated["catalog"]["modalities"]["wgs"]["categories"]["solid"]["catalog_id"] == identifier
    )
    assert service.repository.get_default() is None


def test_modality_import_copies_public_catalog_without_updating_it(service):
    doc = approved(service)
    service.publish(str(doc["_id"]), doc["revision"], actor="publisher")
    before = service.repository.get_default()
    imported = service.create(
        actor="author",
        imported={
            "kind": "coyote3.public_assay_catalog_modality",
            "modality": "wts",
            "definition": {"label": "Whole Transcriptome Sequencing (WTS)", "categories": {}},
        },
    )
    assert set(imported["catalog"]["modalities"]) == {"wgs", "wts"}
    assert service.repository.get_default() == before
