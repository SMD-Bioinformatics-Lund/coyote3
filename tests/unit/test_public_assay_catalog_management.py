"""Governance, validation, and public-data isolation for catalog authoring."""

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from bson import ObjectId

from coyote3.application.public.catalog import PublicCatalogService
from coyote3.application.public.published_catalog_views import (
    publication_context,
    publication_matrix,
)
from coyote3.application.resources.public_assay_catalog import PublicAssayCatalogManagementService
from coyote3.config.constants import DNA_ANALYSIS_TYPE_OPTIONS, RNA_ANALYSIS_TYPE_OPTIONS
from coyote3.contracts.public import PublicAssayCatalogAdminPayload
from coyote3.domain.exceptions import AppError as ApiError


@pytest.mark.parametrize(
    ("short_name", "display_name", "expected"),
    [
        ("SG3", "Full assay name", "SG3"),
        (None, "Full assay name", "Full assay name"),
        ("  ", "", "assay"),
    ],
)
def test_published_assay_labels_prefer_short_name_then_display_name_then_id(
    service, short_name, display_name, expected
):
    """Catalog and matrix use the reviewed assay label without altering gene-list identity."""
    panels = service.assay_panel_repository.get_all_asps()
    panels[0].update(name=short_name, display_name=display_name)
    service.assay_panel_repository.get_all_asps = lambda **kwargs: panels
    publication = service.preview_offerings(content(), actor="author")
    assert publication["offerings"][0]["assay_label"] == expected
    assert publication["offerings"][0]["assay_display_name"] == (
        display_name.strip() or (short_name or "").strip() or panels[0]["asp_id"]
    )
    assert publication_matrix(publication)["columns"][0]["assay"] == expected
    column = publication_matrix(publication)["columns"][0]
    assert column["assay_id"] == panels[0]["asp_id"]
    assert column["diagnosis_id"] == publication["offerings"][0]["diagnosis_id"]


def test_reviewed_scope_and_price_are_frozen_and_private_fields_are_separate(service):
    """Publication exposes effective genes and price without operational configuration."""
    source = content()
    source["modalities"]["wgs"]["categories"]["solid"]["price"] = {
        "amount": "123.45",
        "currency": "EUR",
        "kind": "starting",
    }
    lists = service.gene_list_repository.get_all_isgl()
    lists[0]["genes"] = ["GENE1", "OUTSIDE"]
    lists[0]["name"] = "DG"
    service.gene_list_repository.get_all_isgl = lambda **kw: lists
    doc = service.create(actor="author", imported=source)
    doc = service.submit(str(doc["_id"]), doc["revision"], "reviewer", actor="author")
    item = doc["catalog"]["published_offerings"][0]
    assert item["gene_scopes"][0]["genes"] == ["GENE1"]
    assert item["gene_scopes"][0]["excluded_gene_count"] == 1
    assert item["price"]["amount"] == "123.45"
    publication = {"version": 1, "header": "Services", "description": "", "offerings": [item]}
    matrix = publication_matrix(publication)
    assert matrix["genes"] == ["GENE1"]
    assert matrix["columns"][0]["analysis"] == "SNV"
    assert matrix["columns"][0]["isgl_label"] == "DG"
    assert publication_matrix(publication, gene="OUTSIDE")["total"] == 0
    context = publication_context(publication, "dna", item["offering_id"])
    assert [row["symbol"] for row in context["genes"]] == ["GENE1"]
    assert not {"filters", "configuration_id", "aspc_id", "resource_revisions"} & item.keys()
    doc = service.decide(
        str(doc["_id"]),
        doc["revision"],
        actor="reviewer",
        approve=True,
        publisher="publisher",
        reason="Reviewed",
    )
    service.publish(str(doc["_id"]), doc["revision"], actor="publisher")
    lists[0]["genes"] = ["REPLACED"]
    assert service.repository.get_default()["published_offerings"][0] == item
    assert service.preview_offerings(doc["catalog"], actor="reviewer")["offerings"][0] == item
    reader = PublicCatalogService(
        assay_panel_repository=None,
        hgnc_repository=None,
        gene_list_repository=None,
        sample_repository=None,
        vep_metadata_repository=None,
        public_assay_catalog_repository=service.repository,
    )
    assert reader.published_offerings()["offerings"] == [item]
    assert "resource_revisions" not in reader.published_offerings()
    assert reader.published_matrix()["genes"] == ["GENE1"]
    assert reader.assay_catalog_gene_symbols_payload("diagnosis") == {"gene_symbols": ["GENE1"]}


def test_published_matrix_resolves_markers_only_for_visible_published_genes(service):
    """Annotation membership is batched per page without changing reviewed gene coverage."""
    publication = service.preview_offerings(content(), actor="author")
    publication["offerings"][0]["gene_scopes"][0]["genes"] = ["GENE1", "GENE2"]
    reader = PublicCatalogService(
        assay_panel_repository=None,
        hgnc_repository=None,
        gene_list_repository=None,
        sample_repository=None,
        vep_metadata_repository=None,
    )
    reader.published_offerings = lambda: publication
    oncokb = Mock(return_value={"GENE2": {"gene": "GENE2", "private_field": "hidden"}})
    cosmic = Mock(return_value={"GENE2": {"gene": "GENE2"}})
    civic = Mock(return_value={"GENE2": {"gene": "GENE2"}})
    clinpgx = Mock(return_value={"GENE2": {"pharmgkb_accession_id": "PA2"}})
    reader.oncokb_public_cache_repository = SimpleNamespace(get_gene_records=oncokb)
    reader.cosmic_repository = SimpleNamespace(get_cancer_gene_census_records=cosmic)
    reader.civic_repository = SimpleNamespace(get_gene_records=civic)
    reader.clinpgx_public_repository = SimpleNamespace(get_gene_records=clinpgx)

    matrix = reader.published_matrix(page=2, per_page=1)

    assert matrix["genes"] == ["GENE2"]
    assert matrix["gene_markers"] == {
        "GENE2": {
            "oncokb": True,
            "cosmic_cgc": True,
            "civic": True,
            "clinpgx": True,
            "clinpgx_accession": "PA2",
        }
    }
    assert matrix["matrix"] == publication_matrix(publication, page=2, per_page=1)["matrix"]
    for lookup in (oncokb, cosmic, civic, clinpgx):
        lookup.assert_called_once_with(["GENE2"])
        lookup.reset_mock()
    assert reader.published_matrix(gene="NOT_PUBLISHED")["gene_markers"] == {}
    for lookup in (oncokb, cosmic, civic, clinpgx):
        lookup.assert_not_called()


def test_published_matrix_without_knowledgebases_returns_no_positive_markers(service):
    """Missing optional knowledgebases do not create source membership or hide coverage."""
    reader = PublicCatalogService(
        assay_panel_repository=None,
        hgnc_repository=None,
        gene_list_repository=None,
        sample_repository=None,
        vep_metadata_repository=None,
    )
    reader.published_offerings = lambda: service.preview_offerings(content(), actor="author")
    matrix = reader.published_matrix()
    assert matrix["genes"] == ["GENE1"]
    assert matrix["gene_markers"]["GENE1"] == {
        "oncokb": False,
        "cosmic_cgc": False,
        "civic": False,
        "clinpgx": False,
        "clinpgx_accession": None,
    }


def test_source_revision_change_after_review_requires_new_review(service):
    """A reviewed release cannot publish against silently changed source revisions."""
    doc = approved(service)
    panels = service.assay_panel_repository.get_all_asps()
    panels[0]["version"] += 1
    service.assay_panel_repository.get_all_asps = lambda **kw: panels
    with pytest.raises(ApiError) as error:
        service.publish(str(doc["_id"]), doc["revision"], actor="publisher")
    assert error.value.status_code == 409
    assert service.repository.get_default() is None


def test_import_cannot_supply_a_publication_snapshot(service):
    """Client-supplied derived scope is discarded before governance begins."""
    source = content()
    source.update(published_offerings=[{"title": "Unreviewed"}], resource_revisions={"fake": {}})
    doc = service.create(actor="author", imported=source)
    assert doc["catalog"]["published_offerings"] == []
    assert doc["catalog"]["resource_revisions"] == {}
    with pytest.raises(ApiError) as error:
        service.preview_offerings(source, actor="author")
    assert error.value.status_code == 422


def test_offering_cannot_advertise_unselected_gene_scope(service):
    """Public list bindings must be selected by the production analysis configuration."""
    configs = service.assay_configuration_repository.get_all_aspc()
    configs[0]["filters"] = {}
    service.assay_configuration_repository.get_all_aspc = lambda: configs
    doc = draft(service)
    with pytest.raises(ApiError):
        service.submit(str(doc["_id"]), doc["revision"], "reviewer", actor="author")


def test_offering_cannot_advertise_disabled_analysis(service):
    """Assay capability alone does not enable a production offering analysis."""
    configs = service.assay_configuration_repository.get_all_aspc()
    configs[0]["analysis_types"] = ["CNV"]
    service.assay_configuration_repository.get_all_aspc = lambda: configs
    doc = draft(service)
    with pytest.raises(ApiError):
        service.submit(str(doc["_id"]), doc["revision"], "reviewer", actor="author")


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
        groups=SimpleNamespace(
            get=lambda key: {
                "group_id": key,
                "display_name": "Demo",
                "version": 1,
                "is_active": True,
            }
        ),
        diagnoses=SimpleNamespace(list_for_assay=lambda *args, **kwargs: []),
        assay_panel_repository=SimpleNamespace(
            get_all_asps=lambda **kw: [
                {
                    "asp_id": "assay",
                    "asp_group": "demo",
                    "asp_category": "dna",
                    "asp_family": "wgs",
                    "version": 1,
                    "is_active": True,
                    "display_name": "Assay",
                    "covered_genes": ["GENE1"],
                    "supported_analyses": ["SNV", "CNV"],
                }
            ],
            group_options=lambda: ["demo"],
        ),
        assay_configuration_repository=SimpleNamespace(
            get_all_aspc=lambda: [
                {
                    "asp_id": "assay",
                    "aspc_id": "assay_base",
                    "asp_group": "demo",
                    "version": 1,
                    "diagnosis_id": "base",
                    "analysis_types": ["SNV", "CNV"],
                    "filters": {
                        "somatic": {
                            "snv": {"snvlists": ["diagnosis"]},
                            "cnv": {"cnvlists": ["diagnosis"]},
                        }
                    },
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
            get_all_isgl=lambda **kw: [
                {
                    "isgl_id": "diagnosis",
                    "displayname": "Diagnosis genes",
                    "version": 1,
                    "genes": ["GENE1"],
                    "list_type": ["snv", "cnv"],
                    "asp_ids": ["assay"],
                    "asp_groups": ["demo"],
                }
            ]
        ),
    )
    service.notification_service = Mock()
    service.assay_panel_repository.get_asp = lambda key: next(
        (x for x in service.assay_panel_repository.get_all_asps() if x["asp_id"] == key), None
    )
    service.assay_configuration_repository.get_aspc_with_id = lambda key: next(
        (x for x in service.assay_configuration_repository.get_all_aspc() if x["aspc_id"] == key),
        None,
    )
    service.gene_list_repository.get_isgl = lambda key, **kw: next(
        (x for x in service.gene_list_repository.get_all_isgl() if x["isgl_id"] == key), None
    )
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
                        "analysis": ["SNV"],
                        "gene_lists": [{"isgl_id": "diagnosis", "analysis": ["SNV"]}],
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


def test_workspace_response_preserves_omics_specific_analysis_choices(service):
    """Validate the actual workspace against its HTTP response contract."""
    payload = PublicAssayCatalogAdminPayload.model_validate(service.workspace())
    assert payload.presets.analysis_by_omics == {
        "dna": list(DNA_ANALYSIS_TYPE_OPTIONS),
        "rna": list(RNA_ANALYSIS_TYPE_OPTIONS),
    }
    assert payload.model_dump(mode="json")["presets"]["input_material"]


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


def test_analysis_assignments_accept_multiple_lists_and_explicit_none(service):
    """List references can be shared across analyses without copying gene contents."""
    service.gene_list_repository.get_all_isgl = lambda **kw: [
        {"isgl_id": key, "asp_ids": ["assay"], "asp_groups": ["demo"], "list_type": ["snv", "cnv"]}
        for key in ("diagnosis", "second")
    ]
    data = content()
    entry = data["modalities"]["wgs"]["categories"]["solid"]
    entry.update(analysis=["SNV", "CNV", "MSI"], no_gene_list=["MSI"])
    entry["gene_lists"] = [
        {"isgl_id": "diagnosis", "analysis": ["SNV", "CNV"]},
        {"isgl_id": "second", "analysis": ["SNV"]},
    ]
    service.validate_links(data)


def test_inherited_catalog_links_are_validated_at_child_scope(service):
    """Children inherit links, but cannot silently reuse them with another assay."""
    data = content()
    entries = data["modalities"]["wgs"]["categories"]
    entries["child"] = {"label": "Child", "parent_key": "solid"}
    service.validate_links(data)
    entries["child"]["asp_id"] = "other_assay"
    with pytest.raises(ApiError, match="active assay"):
        service.validate_links(data)


def test_general_lists_are_valid_without_analysis_assignments(service):
    """An entry may inherit an assay-linked general list without inventing analysis tabs."""
    data = content()
    entries = data["modalities"]["wgs"]["categories"]
    entries["solid"]["analysis"] = []
    entries["solid"]["gene_lists"] = [{"isgl_id": "diagnosis", "analysis": []}]
    entries["child"] = {"label": "Child", "parent_key": "solid"}
    service.validate_links(data)


def test_rna_catalog_rejects_dna_analysis_and_wrong_list_type(service):
    """Publication checks software capabilities and each ISGL's supported analyses."""
    data = content()
    service.assay_panel_repository.get_all_asps = lambda **kw: [
        {"asp_id": "assay", "asp_group": "demo", "asp_category": "rna"}
    ]
    with pytest.raises(ApiError, match="DNA/RNA"):
        service.validate_links(data)
    entry = data["modalities"]["wgs"]["categories"]["solid"]
    entry["analysis"] = ["FUSION"]
    entry["gene_lists"][0]["analysis"] = ["FUSION"]
    with pytest.raises(ApiError, match="Gene-list types"):
        service.validate_links(data)


@pytest.mark.parametrize(
    "problem", ["missing", "conflict", "wrong_group", "wrong_assay", "unselected"]
)
def test_invalid_analysis_assignments_block_submission(service, problem):
    """Publication rejects incomplete mappings, contradictions and ineligible lists."""
    data = content()
    entry = data["modalities"]["wgs"]["categories"]["solid"]
    if problem == "missing":
        entry["analysis"].append("CNV")
    elif problem == "conflict":
        entry["no_gene_list"] = ["SNV"]
    elif problem == "unselected":
        entry["gene_lists"][0]["analysis"] = ["CNV"]
    else:
        service.gene_list_repository.get_all_isgl = lambda **kw: [
            {
                "isgl_id": "diagnosis",
                "asp_ids": ["other" if problem == "wrong_assay" else "assay"],
                "asp_groups": ["other" if problem == "wrong_group" else "demo"],
            }
        ]
    with pytest.raises(ApiError):
        service.validate_links(data)


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
