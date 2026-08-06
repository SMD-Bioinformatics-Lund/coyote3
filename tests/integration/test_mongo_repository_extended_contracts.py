from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import mongomock
import pytest
from bson import ObjectId

from api.infra.mongo.repositories.assay_configurations import ASPConfigRepository
from api.infra.mongo.repositories.assay_panels import ASPRepository
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.repositories.copy_number_variants import CNVsRepository
from api.infra.mongo.repositories.fusions import FusionsRepository
from api.infra.mongo.repositories.gene_lists import ISGLRepository
from api.infra.mongo.repositories.permissions import PermissionsRepository
from api.infra.mongo.repositories.roles import RolesRepository
from api.infra.mongo.repositories.samples import SampleRepository
from api.infra.mongo.repositories.translocations import TranslocsRepository
from api.infra.mongo.repositories.users import UsersRepository
from api.infra.mongo.repositories.variants import VariantsRepository


class _Cache:
    def __init__(self) -> None:
        self.values: dict[str, object] = {}

    def get(self, key: str):
        return self.values.get(key)

    def set(self, key: str, value: object, timeout: int = 0) -> None:
        _ = timeout
        self.values[key] = value

    def delete(self, key: str) -> None:
        self.values.pop(key, None)

    def clear(self) -> None:
        self.values.clear()


def _adapter():
    database = mongomock.MongoClient()["coyote3_repository_contracts"]
    app = SimpleNamespace(
        config={"CACHE_DEFAULT_TIMEOUT": 60},
        cache=_Cache(),
        logger=logging.getLogger("repository-contracts"),
        home_logger=logging.getLogger("repository-contracts"),
    )
    names = {
        "roles_collection": "roles",
        "permissions_collection": "permissions",
        "assay_panels_collection": "assay_panels",
        "asp_collection": "assay_panels",
        "assay_configurations_collection": "assay_configurations",
        "aspc_collection": "assay_configurations",
        "insilico_genelist_collection": "insilico_genelists",
        "fusions_collection": "fusions",
        "copy_number_variants_collection": "copy_number_variants",
        "cnvs_collection": "copy_number_variants",
        "translocations_collection": "translocations",
        "translocs_collection": "translocations",
        "transloc_collection": "translocations",
        "annotations_collection": "annotations",
        "samples_collection": "samples",
        "users_collection": "users",
        "variants_collection": "variants",
    }
    adapter = SimpleNamespace(app=app, coyote_db=database)
    for attribute, collection_name in names.items():
        setattr(adapter, attribute, database[collection_name])
    return adapter


class _SampleCommentRepository:
    def __init__(self) -> None:
        self.added: list[tuple[dict, dict]] = []
        self.hidden: list[tuple[str, str, bool]] = []

    def add_sample_comment(self, *, sample: dict, comment_doc: dict) -> None:
        self.added.append((sample, comment_doc))

    def set_hidden(self, *, sample_oid: str, comment_id: str, hidden: bool) -> None:
        self.hidden.append((sample_oid, comment_id, hidden))

    def hidden_sample_comments(self, sample_id: str) -> bool:
        return sample_id == "hidden"

    def get_latest_sample_comment(self, sample_id: str) -> dict:
        return {"sample_id": sample_id, "text": "latest"}


class _ReportRepository:
    def __init__(self) -> None:
        self.saved: list[dict] = []

    def save_report(self, **kwargs):
        self.saved.append(kwargs)
        return True

    def get_report(self, sample_id: str, report_id: str) -> dict:
        return {"sample_id": sample_id, "report_id": report_id}


def test_base_repository_mutations_bulk_validation_and_comments(monkeypatch) -> None:
    adapter = _adapter()
    repository = BaseRepository(adapter)
    collection = adapter.coyote_db["findings"]
    repository.set_collection(collection)
    comment_id = ObjectId()
    finding_id = collection.insert_one(
        {
            "comments": [
                {"_id": comment_id, "hidden": 0, "time_created": datetime(2025, 1, 1)},
                {"_id": ObjectId(), "hidden": 1, "time_created": datetime(2025, 1, 2)},
            ]
        }
    ).inserted_id
    monkeypatch.setattr("api.infra.mongo.repositories.base.current_username", lambda: "curator")

    assert repository.mark_false_positive(str(finding_id), True).modified_count == 1
    assert repository.mark_interesting(str(finding_id), True).modified_count == 1
    assert repository.mark_irrelevant(str(finding_id), True).modified_count == 1
    assert repository.mark_blacklisted(str(finding_id), True).modified_count == 1
    assert repository.mark_noteworthy(str(finding_id), True).modified_count == 1
    assert repository.hidden_comments(str(finding_id)) is True
    assert repository.get_latest_comment(str(finding_id))["hidden"] == 1

    for method, field in (
        (repository.mark_false_positive_bulk, "fp"),
        (repository.mark_irrelevant_bulk, "irrelevant"),
        (repository.mark_blacklisted_bulk, "blacklisted"),
    ):
        assert method([], True).requested_count == 0
        assert method(["invalid"], True).matched_count == 0
        result = method([str(finding_id), "invalid"], False)
        assert result.matched_count == 1
        assert collection.find_one({"_id": finding_id})[field] is False

    inserted = repository.add_comment({"text": "global"})
    assert inserted.inserted_id is not None
    assert repository.update_comment(str(finding_id), {"text": "sample"}).modified_count == 1
    assert repository.hidden_comments(str(collection.insert_one({}).inserted_id)) is False
    assert (
        repository.get_latest_comment(str(collection.insert_one({"comments": []}).inserted_id))
        is None
    )


def test_base_repository_requires_a_bound_collection() -> None:
    with pytest.raises(NotImplementedError):
        BaseRepository(_adapter()).get_collection()


def test_permissions_repository_search_validation_and_lifecycle() -> None:
    adapter = _adapter()
    repository = PermissionsRepository(adapter)
    repository.ensure_indexes()
    repository.create_new_policy(
        {
            "permission_id": " SAMPLE:READ ",
            "label": "Read samples",
            "category": "Samples",
            "description": "Read clinical samples",
            "is_active": True,
        }
    )
    repository.create_new_policy(
        {
            "permission_id": "sample:delete",
            "label": "Delete samples",
            "category": "Samples",
            "is_active": False,
        }
    )

    assert repository.get_permission("SAMPLE:READ")["permission_id"] == "sample:read"
    assert repository.is_valid(" sample:read ") is True
    assert repository.is_valid("missing") is False
    assert repository.get_categories() == ["Samples"]
    assert [row["permission_id"] for row in repository.get_by_category("Samples")] == [
        "sample:read"
    ]
    assert len(repository.get_all_permissions()) == 1
    assert len(repository.get_all_permissions(is_active=False)) == 2
    rows, total = repository.search_permissions(q="delete", page=0, per_page=500)
    assert total == 1 and rows[0]["permission_id"] == "sample:delete"
    active_rows, active_total = repository.search_permissions(is_active=True)
    assert active_total == 1 and active_rows[0]["permission_id"] == "sample:read"

    repository.update_policy(
        "sample:read",
        {"permission_id": "sample:read", "label": "View samples", "is_active": True},
    )
    assert repository.get_permission("sample:read")["label"] == "View samples"
    repository.toggle_policy_active("sample:delete", True)
    assert repository.get_permission("sample:delete")["is_active"] is True
    repository.delete_policy("sample:delete")
    assert repository.get_permission("sample:delete")["is_active"] is False
    with pytest.raises(ValueError):
        repository.ensure_permission_id({})
    assert repository._permission_lookup_query("") == {"permission_id": None}


def test_roles_repository_search_colors_permissions_and_lifecycle(monkeypatch) -> None:
    adapter = _adapter()
    repository = RolesRepository(adapter)
    monkeypatch.setattr(
        "api.infra.mongo.repositories.roles.invalidate_dashboard_summary_cache", lambda *_: None
    )
    repository.ensure_indexes()
    repository.create_role(
        {
            "role_id": " Manager ",
            "label": "Manager",
            "description": "Delegated manager",
            "level": 50,
            "color": "#445566",
            "permissions": ["sample:read"],
            "is_active": True,
        }
    )
    adapter.roles_collection.insert_one(
        {"role_id": "hidden", "level": 1, "is_active": False, "color": "#000000"}
    )

    assert repository.count_roles() == 2
    assert repository.count_roles(True) == 1
    assert repository.get_all_role_names() == ["manager"]
    assert repository.get_role_colors() == {"manager": "#445566"}
    rows, total = repository.search_roles(q="delegated", page=0, per_page=500)
    assert total == 1 and rows[0]["role_id"] == "manager"
    assert repository.get_role_permissions("MANAGER")["permissions"] == ["sample:read"]
    assert repository.get_all_roles_plus_permissions()[0]["role_id"] == "manager"

    updated = repository.update_role(
        "manager",
        {
            "role_id": "manager",
            "label": "Clinical manager",
            "level": 55,
            "is_active": True,
        },
    )
    assert updated["label"] == "Clinical manager"
    assert repository.get_role("") is None
    repository.toggle_role_active("manager", False)
    assert repository.get_role("manager") is None
    adapter.roles_collection.update_one({"role_id": "manager"}, {"$set": {"is_active": True}})
    assert repository.delete_role("manager").modified_count == 1
    with pytest.raises(ValueError):
        repository.ensure_role_id({"label": "missing"})


def test_fusion_repository_selection_annotations_matching_and_mutations(monkeypatch) -> None:
    adapter = _adapter()
    repository = FusionsRepository(adapter)
    repository.ensure_indexes()
    sample_a = adapter.samples_collection.insert_one({"name": "A", "asp_id": "rna"}).inserted_id
    sample_b = adapter.samples_collection.insert_one({"name": "B", "asp_id": "rna"}).inserted_id
    fusion_a = adapter.fusions_collection.insert_one(
        {
            "SAMPLE_ID": str(sample_a),
            "genes": ["ETV6", "RUNX1"],
            "calls": [
                {
                    "selected": 1,
                    "breakpoint1": "1:10:+",
                    "breakpoint2": "2:20:-",
                    "spanreads": 4,
                    "spanpairs": 3,
                },
                {"selected": 0, "breakpoint1": "1:11:+", "breakpoint2": "2:21:-"},
            ],
            "comments": [],
        }
    ).inserted_id
    adapter.fusions_collection.insert_one(
        {
            "SAMPLE_ID": str(sample_b),
            "genes": ["ETV6", "RUNX1"],
            "calls": [
                {
                    "selected": 1,
                    "breakpoint1": "2:20:-",
                    "breakpoint2": "1:10:+",
                    "spanreads": 8,
                    "spanpairs": 6,
                }
            ],
            "fp": True,
        }
    )
    adapter.annotations_collection.insert_many(
        [
            {"variant": "1:10:+^2:20:-", "text": "note", "time_created": 1},
            {"variant": "1:10:+^2:20:-", "class": 2, "time_created": 2},
        ]
    )

    fusion = repository.get_fusion(str(fusion_a))
    assert repository.get_selected_fusioncall(fusion)["spanreads"] == 4
    assert repository.get_selected_fusioncall({"calls": []}) is None
    notes, classification = repository.get_fusion_annotations(fusion)
    assert notes[0]["text"] == "note" and classification["class"] == 2
    assert repository.get_fusion_annotations({"calls": []}) == ([], {"class": 999})
    assert repository.get_total_fusion_count() == 2
    assert repository.get_unique_fusion_count() == 1

    class _ProjectionCompatibleCollection:
        def find(self, query, _projection=None):
            return adapter.fusions_collection.find(query)

    monkeypatch.setattr(repository, "get_collection", lambda: _ProjectionCompatibleCollection())
    assert (
        len(repository.find_fusions_with_matching_breakpoints(str(sample_a), "1:10:+", "2:20:-"))
        == 1
    )
    monkeypatch.undo()
    matching = list(adapter.fusions_collection.find({"SAMPLE_ID": str(sample_b)}))
    monkeypatch.setattr(
        repository, "find_fusions_with_matching_breakpoints", lambda **_kwargs: matching
    )
    other = repository.get_fusion_in_other_samples(fusion)
    assert other[0]["sample_name"] == "B" and other[0]["spanning_pairs"] == 6
    assert repository.get_fusion_in_other_samples({"SAMPLE_ID": str(sample_a), "calls": []}) == []

    repository.pick_fusion(str(fusion_a), 2, 2)
    assert repository.get_fusion(str(fusion_a))["calls"][1]["selected"] == 1
    repository.mark_false_positive_fusion(str(fusion_a))
    repository.unmark_false_positive_fusion(str(fusion_a))
    repository.add_fusion_comment(str(fusion_a), {"text": "reviewed"})
    assert repository.get_fusion(str(fusion_a))["comments"][0]["text"] == "reviewed"
    assert repository.delete_sample_fusions(str(sample_b)).deleted_count == 1


def test_structural_repositories_normalize_query_and_mutate_records() -> None:
    adapter = _adapter()
    cnvs = CNVsRepository(adapter)
    translocations = TranslocsRepository(adapter)
    cnvs.ensure_indexes()
    translocations.ensure_indexes()
    cnv_id = adapter.copy_number_variants_collection.insert_one(
        {"SAMPLE_ID": "sample", "genes": ["MYC"], "comments": [], "interesting": True}
    ).inserted_id
    translocation_id = adapter.translocations_collection.insert_one(
        {
            "SAMPLE_ID": "sample",
            "INFO": [{"CSQ": [{"SYMBOL": "NTRK1"}]}],
            "comments": [],
            "interesting": True,
        }
    ).inserted_id

    assert cnvs.get_cnv(str(cnv_id))["genes"] == ["MYC"]
    assert cnvs.get_sample_cnvs({"SAMPLE_ID": "sample"})[0]["genes"] == ["MYC"]
    assert len(list(cnvs.get_interesting_sample_cnvs("sample"))) == 1
    assert cnvs.get_total_cnv_count() == 1 and cnvs.get_unique_cnv_count() == 1
    cnvs.mark_interesting_cnv(str(cnv_id), False)
    cnvs.mark_false_positive_cnv(str(cnv_id), True)
    cnvs.noteworthy_cnv(str(cnv_id), True)
    cnvs.add_cnv_comment(str(cnv_id), {"text": "cnv"})
    assert cnvs.get_cnv(str(cnv_id))["comments"][0]["text"] == "cnv"

    normalized = translocations.get_transloc(str(translocation_id))
    assert isinstance(normalized["INFO"], dict)
    assert (
        translocations.get_sample_translocations("sample")[0]["INFO"]["CSQ"][0]["SYMBOL"] == "NTRK1"
    )
    assert len(list(translocations.get_interesting_sample_translocations("sample"))) == 1
    assert translocations.get_total_transloc_count() == 1
    assert translocations.get_unique_transloc_count() == 1
    translocations.mark_interesting_transloc(str(translocation_id), False)
    translocations.mark_false_positive_transloc(str(translocation_id), True)
    translocations.add_transloc_comment(str(translocation_id), {"text": "translocation"})
    assert (
        translocations.get_transloc(str(translocation_id))["comments"][0]["text"] == "translocation"
    )


def test_asp_repository_business_keys_scope_genes_and_lifecycle(monkeypatch) -> None:
    adapter = _adapter()
    repository = ASPRepository(adapter)
    monkeypatch.setattr(
        "api.infra.mongo.repositories.assay_panels.invalidate_dashboard_summary_cache",
        lambda *_: None,
    )
    repository.create_panel(
        {
            "asp_id": " HEMA_GMSV1 ",
            "display_name": "Hematology",
            "asp_group": "hematology",
            "asp_family": "panel-dna",
            "asp_category": "dna",
            "platform": "illumina",
            "covered_genes": ["TP53", "FLT3", ""],
            "germline_genes": ["CEBPA"],
            "is_active": True,
            "created_on": datetime(2025, 1, 1),
        }
    )
    repository.create_panel(
        {
            "asp_id": "solid_gmsv3",
            "display_name": "Solid",
            "asp_group": "solid",
            "covered_genes": ["TP53", "KRAS"],
            "is_active": True,
            "created_on": datetime(2025, 1, 2),
        }
    )
    adapter.assay_panels_collection.insert_one(
        {"asp_id": "retired", "asp_group": "solid", "is_active": False}
    )

    assert repository.count_asps() == 3
    assert repository.count_asps(True) == 2
    assert repository.get_asp("HEMA_GMSV1")["asp_id"] == "hema_gmsv1"
    assert repository.resolve_active_asp_ids_for_scope(["solid_gmsv3"], []) == ["solid_gmsv3"]
    assert set(repository.resolve_active_asp_ids_for_scope([], ["solid"])) == {"solid_gmsv3"}
    assert repository.resolve_active_asp_ids_for_scope([], []) == []
    assert len(repository.get_all_asps(True)) == 2
    rows, total = repository.search_asps(q="illumina", page=0, per_page=500)
    assert total == 1 and rows[0]["asp_id"] == "hema_gmsv1"
    assert repository.get_all_asps_unique_gene_count() == 3
    assert set(repository.get_all_asp_groups()) == {"hematology", "solid"}
    assert set(repository.get_all_assays(True)) == {"hema_gmsv1", "solid_gmsv3"}
    assert repository.get_asp_genes("hema_gmsv1") == (["TP53", "FLT3", ""], ["CEBPA"])
    assert repository.get_asp_genes("missing") == ([], [])
    assert repository.get_asp_group_mappings()["solid_gmsv3"] == "solid"

    adapter.assay_panels_collection.update_one({"asp_id": "hema_gmsv1"}, {"$set": {"version": 1}})
    repository.rotate_asp(
        "hema_gmsv1",
        {
            "asp_id": "hema_gmsv1",
            "display_name": "Hematology updated",
            "asp_group": "hematology",
            "is_active": True,
            "version": 2,
        },
        expected_version=1,
        retire_fields={"retired_by": "tester", "retired_reason": "superseded_by_edit"},
    )
    assert repository.get_asp("hema_gmsv1")["display_name"] == "Hematology updated"
    assert adapter.assay_panels_collection.count_documents({"asp_id": "hema_gmsv1"}) == 2
    assert (
        adapter.assay_panels_collection.count_documents({"asp_id": "hema_gmsv1", "is_active": True})
        == 1
    )
    repository.toggle_asp_active("hema_gmsv1", False)
    assert repository.get_asp("hema_gmsv1") is None
    repository.toggle_asp_active("hema_gmsv1", True)
    assert repository.get_asp("hema_gmsv1")["version"] == 2
    assert repository.delete_panel("hema_gmsv1").modified_count == 1
    with pytest.raises(ValueError):
        repository.ensure_asp_id({})


def test_aspc_repository_business_keys_queries_and_lifecycle(monkeypatch) -> None:
    adapter = _adapter()
    repository = ASPConfigRepository(adapter)
    monkeypatch.setattr(
        "api.infra.mongo.repositories.assay_configurations.invalidate_dashboard_summary_cache",
        lambda *_: None,
    )
    assert repository.build_aspc_id("HEMA_GMSV1", "Production", "Hem-Snabb") == (
        "hema_gmsv1_hem-snabb_production"
    )
    repository.create_assay_config(
        {
            "asp_id": "HEMA_GMSV1",
            "subpanel_id": "Hem-Snabb",
            "environment": "production",
            "analysis_types": ["SNV", "CNV"],
            "reporting": {"report_sections": ["SNV"]},
            "is_active": True,
        }
    )
    repository.create_assay_config(
        {
            "asp_id": "hema_gmsv1",
            "subpanel_id": "base",
            "environment": "testing",
            "is_active": True,
        }
    )
    aspc_id = "hema_gmsv1_hem-snabb_production"
    assert repository.count_aspcs() == 2
    assert repository.get_aspc("hema_gmsv1", "production", "hem-snabb")["aspc_id"] == aspc_id
    assert repository.get_aspc_with_id(aspc_id)["subpanel_id"] == "hem-snabb"
    assert "created_on" not in repository.get_aspc_no_meta("hema_gmsv1", "production", "hem-snabb")
    assert len(repository.get_active_aspcs_for_asp("hema_gmsv1", "production")) == 1
    assert repository.get_active_aspcs_for_asp("", "production") == []
    rows, total = repository.search_aspcs(q="hem-snabb", page=0, per_page=500)
    assert total == 1 and rows[0]["aspc_id"] == aspc_id
    assert set(repository.get_all_assay_names(True)) == {"hema_gmsv1"}
    assert repository.get_available_assay_envs(
        "hema_gmsv1", ["production", "testing", "validation"], "hem-snabb"
    ) == ["testing", "validation"]

    adapter.assay_configurations_collection.update_one(
        {"aspc_id": aspc_id}, {"$set": {"version": 1}}
    )
    repository.rotate_aspc(
        aspc_id,
        {
            "aspc_id": aspc_id,
            "asp_id": "hema_gmsv1",
            "subpanel_id": "hem-snabb",
            "environment": "production",
            "analysis_types": ["SNV"],
            "is_active": True,
            "version": 2,
        },
        expected_version=1,
        retire_fields={"retired_by": "tester", "retired_reason": "superseded_by_edit"},
    )
    assert repository.get_aspc_with_id(aspc_id)["analysis_types"] == ["SNV"]
    assert adapter.assay_configurations_collection.count_documents({"aspc_id": aspc_id}) == 2
    assert (
        adapter.assay_configurations_collection.count_documents(
            {"aspc_id": aspc_id, "is_active": True}
        )
        == 1
    )
    repository.toggle_aspc_active(aspc_id, False)
    assert repository.get_aspc_with_id(aspc_id) is None
    repository.toggle_aspc_active(aspc_id, True)
    assert repository.get_aspc_with_id(aspc_id)["version"] == 2
    assert repository.delete_assay_config(aspc_id).modified_count == 1
    with pytest.raises(ValueError):
        repository.ensure_aspc_id({})


def test_isgl_repository_scope_gene_selection_and_lifecycle(monkeypatch) -> None:
    adapter = _adapter()
    repository = ISGLRepository(adapter)
    monkeypatch.setattr(
        "api.infra.mongo.repositories.gene_lists.invalidate_dashboard_summary_cache",
        lambda *_: None,
    )
    repository.create_genelist(
        {
            "isgl_id": " HEM ",
            "name": "Hematology",
            "displayname": "Hematology",
            "description": "Myeloid genes",
            "asp_ids": ["hema_gmsv1"],
            "asp_groups": ["hematology"],
            "diagnosis": ["hem", "mpn"],
            "list_type": ["snv", "cnv", "fusion"],
            "genes": ["TP53", "FLT3"],
            "germline_genes": ["CEBPA"],
            "is_public": True,
            "is_active": True,
            "adhoc": False,
            "created_on": datetime(2025, 1, 1),
        }
    )
    repository.create_genelist(
        {
            "isgl_id": "solid",
            "name": "Solid",
            "asp_ids": ["solid_gmsv3"],
            "asp_groups": ["solid"],
            "diagnosis": ["colon"],
            "list_type": ["snv"],
            "genes": ["KRAS", "TP53"],
            "is_public": False,
            "is_active": True,
            "adhoc": True,
            "created_on": datetime(2025, 1, 2),
        }
    )

    assert repository.count_isgls() == 2
    assert repository.count_isgls(is_public=True) == 1
    assert repository.get_isgl("HEM", True, True)["isgl_id"] == "hem"
    assert len(repository.get_all_isgl(adhoc=True)) == 1
    rows, total = repository.search_isgls(q="myeloid", page=0, per_page=500)
    assert total == 1 and rows[0]["isgl_id"] == "hem"
    assert repository.get_subpanels_for_asp(["hema_gmsv1"], True, False) == ["hem", "mpn"]
    assert repository.get_asp_subpanel_genes("hema_gmsv1", "hem") == ["TP53", "FLT3"]
    assert repository.get_asp_subpanel_genes("missing", "hem") == []
    assert repository.get_all_subpanels() == ["colon", "hem", "mpn"]
    assert set(repository.get_all_subpanel_genes(["hem", "colon"])) == {"TP53", "FLT3", "KRAS"}
    assert repository.isgl_exists("hem") is True
    assert len(repository.get_isgl_by_asp("hema_gmsv1", True, False, "snv")) == 1
    assert len(repository.get_isgl_for_scope(assay_group="solid", is_active=True)) == 1
    assert repository.get_isgl_ids("hema_gmsv1", "hem", "snv", True) == ["hem"]
    assert repository.get_isgl_by_ids([]) == {}
    selected = repository.get_isgl_by_ids(["hem"])["hem"]
    assert selected["genes"] == ["TP53", "FLT3"]
    assert repository.get_public_isgl_genes_by_diagnosis("hem") == ["TP53", "FLT3"]
    assert repository.is_isgl_adhoc("solid") is True
    assert repository.get_isgl_display_name("hem") == "Hematology"

    adapter.insilico_genelist_collection.update_one({"isgl_id": "hem"}, {"$set": {"version": 1}})
    repository.rotate_isgl(
        "hem",
        {
            "isgl_id": "hem",
            "name": "Hematology updated",
            "is_active": True,
            "version": 2,
        },
        expected_version=1,
        retire_fields={"retired_by": "tester", "retired_reason": "superseded_by_edit"},
    )
    assert repository.get_isgl("hem")["name"] == "Hematology updated"
    assert adapter.insilico_genelist_collection.count_documents({"isgl_id": "hem"}) == 2
    assert (
        adapter.insilico_genelist_collection.count_documents({"isgl_id": "hem", "is_active": True})
        == 1
    )
    repository.toggle_isgl_active("hem", False)
    assert repository.get_isgl("hem", True) is None
    repository.toggle_isgl_active("hem", True)
    assert repository.get_isgl("hem")["version"] == 2
    assert repository.delete_genelist("hem").modified_count == 1
    with pytest.raises(ValueError):
        repository.ensure_isgl_id({})


def test_users_repository_identity_search_notifications_passwords_and_lifecycle(
    monkeypatch,
) -> None:
    adapter = _adapter()
    repository = UsersRepository(adapter)
    monkeypatch.setattr(
        "api.infra.mongo.repositories.users.invalidate_dashboard_summary_cache", lambda *_: None
    )
    repository.ensure_indexes()
    repository.create_user(
        {
            "username": " CURATOR ",
            "email": "curator@example.test",
            "firstname": "Ada",
            "lastname": "Curator",
            "fullname": "Ada Curator",
            "job_title": "Scientist",
            "roles": ["manager"],
            "auth_type": ["ldap"],
            "is_active": True,
        }
    )
    repository.create_user(
        {
            "username": "viewer",
            "email": "viewer@example.test",
            "firstname": "Zed",
            "roles": ["viewer"],
            "is_active": False,
        }
    )
    assert repository.count_users() == 2 and repository.count_users(True) == 1
    assert repository.user_by_email(" CURATOR@EXAMPLE.TEST ")["username"] == "curator"
    assert repository.user_by_username(" CURATOR ")["email"] == "curator@example.test"
    assert repository.user("curator@example.test")["username"] == "curator"
    assert repository.user("curator")["email"] == "curator@example.test"
    assert repository.user_with_id("CURATOR")["fullname"] == "Ada Curator"
    assert repository.user_by_email("") is None
    assert repository.user_by_username("") is None
    assert repository.user_with_id("") is None
    assert repository.user_exists(email="curator@example.test") is True
    assert repository.user_exists(username="curator") is True
    assert repository.user_exists() is False
    assert len(repository.get_all_users()) == 2
    assert [row["username"] for row in repository.list_active_users_for_notifications()] == [
        "curator"
    ]
    assert len(repository.list_active_users_for_notifications(role_ids=[" MANAGER "])) == 1
    assert repository.list_active_users_for_notifications(role_ids=["admin"]) == []
    rows, total = repository.search_users(q="scientist", page=0, per_page=500)
    assert total == 1 and rows[0]["username"] == "curator"

    assert repository.update_password("curator", "hash").modified_count == 1
    assert repository.user_with_id("curator")["password"] == "hash"
    repository.update_user_last_login("curator")
    assert repository.user_with_id("curator")["last_login"].tzinfo is None
    assert repository.toggle_user_active("curator", False) is True
    assert repository.toggle_user_active("missing", False) is False
    adapter.users_collection.update_one({"username": "curator"}, {"$set": {"is_active": True}})

    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    repository.set_password_action_token(
        user_id="curator",
        token_hash="token",
        purpose="reset",
        expires_at=expires,
        issued_by="admin",
    )
    assert (
        repository.validate_and_clear_password_action_token(
            user_id="curator", token_hash="wrong", purpose="reset"
        )
        is False
    )
    assert (
        repository.validate_and_clear_password_action_token(
            user_id="curator", token_hash="token", purpose="reset"
        )
        is True
    )
    assert (
        repository.validate_and_clear_password_action_token(
            user_id="missing", token_hash="token", purpose="reset"
        )
        is False
    )
    repository.set_password_action_token(
        user_id="curator",
        token_hash="expired",
        purpose="reset",
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    assert (
        repository.validate_and_clear_password_action_token(
            user_id="curator", token_hash="expired", purpose="reset"
        )
        is False
    )

    repository.set_local_password(
        user_id="curator", password_hash="new", require_password_change=True
    )
    user = repository.user_with_id("curator")
    assert user["password"] == "new" and user["auth_type"] == ["ldap", "local"]
    assert user["must_change_password"] is True
    updated = repository.update_user(
        "curator",
        {
            "username": "curator",
            "email": "new@example.test",
            "firstname": "Ada",
            "is_active": True,
        },
    )
    assert updated.modified_count == 1
    assert repository.update_user("missing", {"username": "missing"}).matched_count == 0
    assert repository.delete_user("viewer").deleted_count == 1
    with pytest.raises(ValueError):
        repository.ensure_username({})


def test_samples_repository_lifecycle_scope_counts_versions_and_delegates(monkeypatch) -> None:
    adapter = _adapter()
    adapter.sample_comment_repository = _SampleCommentRepository()
    adapter.report_repository = _ReportRepository()
    repository = SampleRepository(adapter)
    monkeypatch.setattr(
        "api.infra.mongo.repositories.samples.invalidate_samples_cache", lambda *_: None
    )
    monkeypatch.setattr(
        "api.infra.mongo.repositories.samples.invalidate_dashboard_summary_cache", lambda *_: None
    )
    repository.ensure_indexes()
    now = datetime.now(timezone.utc)
    live_id = adapter.samples_collection.insert_one(
        {
            "name": "CASE_A",
            "case_id": "CASE_A",
            "asp_id": "hema_gmsv1",
            "subpanel_id": "hem",
            "environment": "production",
            "ingest_status": "ready",
            "reported": False,
            "time_added": now,
            "paired": True,
            "omics_layer": "dna",
            "sequencing_scope": "panel",
            "pipeline": "SomaticPanelPipeline",
            "pipeline_version": "4.0",
            "database_versions": {"vep": "113", "clinvar": "2026"},
        }
    ).inserted_id
    adapter.samples_collection.insert_many(
        [
            {
                "name": "CASE_B",
                "control_id": "CTRL_B",
                "asp_id": "solid_gmsv3",
                "subpanel_id": "colon",
                "environment": "testing",
                "ingest_status": "ready",
                "reported": True,
                "latest_report_on": now,
                "time_added": now - timedelta(days=1),
                "paired": False,
                "omics_layer": "dna",
                "sequencing_scope": "panel",
                "pipeline": "SomaticPanelPipeline",
                "pipeline_version": "3.2",
                "database_versions": {"vep": "103"},
            },
            {
                "name": "LOADING",
                "asp_id": "fusion",
                "environment": "production",
                "ingest_status": "loading",
                "time_added": now - timedelta(days=2),
                "omics_layer": "rna",
                "sequencing_scope": "wts",
            },
        ]
    )

    assert repository.get_sample("CASE_A")["_id"] == live_id
    assert repository.get_sample(str(live_id))["name"] == "CASE_A"
    assert repository.get_sample("missing") == {}
    assert repository.get_sample_name(str(live_id)) == "CASE_A"
    assert repository.get_sample_by_oid(live_id)["name"] == "CASE_A"
    assert [row["name"] for row in repository.get_samples_by_oids([live_id])] == ["CASE_A"]
    assert repository.count_live_samples_by_asp(
        user_assays=["hema_gmsv1"], user_envs=["production"]
    ) == {"hema_gmsv1": 1}
    assert repository.get_all_sample_counts() == 3
    assert repository.get_all_sample_counts(True) == 1
    assert repository.get_all_sample_counts(False) == 2
    assert repository.user_sample_counts_by_assay(assays=["hema_gmsv1"]) == {"hema_gmsv1": 1}
    assert repository.get_assay_specific_sample_stats(["hema_gmsv1"])["hema_gmsv1"] == {
        "total": 1,
        "analysed": 0,
        "pending": 1,
    }
    assert [row["name"] for row in repository.get_all_samples(limit=1)] == ["CASE_A"]
    assert [row["name"] for row in repository.get_all_samples(["solid_gmsv3"], search_str="B")] == [
        "CASE_B"
    ]
    rows, total = repository.search_samples_for_admin(
        search_str="ctrl_b", ready_only=False, page=0, per_page=500
    )
    assert total == 1 and rows[0]["name"] == "CASE_B"

    repository.reset_sample_settings(
        str(live_id),
        {"_id": "remove", "id_": "remove", "snv": {"min_depth": 100}},
        aspc={"_id": ObjectId(), "aspc_id": "hema_base_production", "version": 2},
    )
    assert repository.get_sample_by_id(str(live_id))["filters"] == {"snv": {"min_depth": 100}}
    repository.update_sample_filters(str(live_id), {"snv": {"min_depth": 50}})
    assert repository.get_sample_by_id(str(live_id))["filters"]["snv"]["min_depth"] == 50
    result = repository.update_sample(
        live_id,
        {
            "name": "CASE_A",
            "asp_id": "hema_gmsv1",
            "ingest_status": "ready",
            "reported": False,
        },
    )
    assert result.matched_count == 1

    repository.add_sample_comment("CASE_A", {"text": "review"})
    repository.hide_sample_comment(str(live_id), "comment")
    repository.unhide_sample_comment(str(live_id), "comment")
    assert adapter.sample_comment_repository.added[0][1]["text"] == "review"
    assert adapter.sample_comment_repository.hidden[-2:] == [
        (str(live_id), "comment", True),
        (str(live_id), "comment", False),
    ]
    assert repository.hidden_sample_comments("hidden") is True
    assert repository.get_latest_sample_comment("CASE_A")["text"] == "latest"
    assert repository.save_report("missing", 1, "r1", "/tmp/report") is None
    assert repository.save_report("CASE_A", 1, "r1", "/tmp/report", "/tmp/report.pdf") is True
    assert repository.get_report("CASE_A", "r1")["report_id"] == "r1"

    assert repository.get_profile_counts() == {None: 1, "production": 1, "testing": 1}
    software = repository.get_observed_software_versions()
    assert software["pipelines"] == {"SomaticPanelPipeline": ["3.2"]}
    assert software["vep"] == ["103"]
    adapter.samples_collection.update_one(
        {"_id": live_id},
        {
            "$set": {
                "pipeline": "SomaticPanelPipeline",
                "pipeline_version": "4.0",
                "database_versions": {"vep": "113", "clinvar": "2026"},
                "environment": "production",
                "paired": True,
                "omics_layer": "dna",
                "sequencing_scope": "panel",
            }
        },
    )
    assert repository.get_observed_software_versions()["pipelines"] == {
        "SomaticPanelPipeline": ["3.2", "4.0"]
    }
    assert repository.get_observed_database_versions() == {
        "clinvar": ["2026"],
        "vep": ["103", "113"],
    }
    assert repository.get_omics_counts() == {"dna": 2, "rna": 1}
    assert repository.get_sequencing_scope_counts() == {"panel": 2, "wts": 1}
    assert repository.get_paired_sample_counts() == {"paired": 1, "unpaired": 1, "unknown": 1}
    assert repository.delete_sample(str(live_id)).deleted_count == 1


def test_variants_repository_identity_cross_sample_mutations_metrics_and_stats(monkeypatch) -> None:
    adapter = _adapter()
    repository = VariantsRepository(adapter)
    repository.ensure_indexes()
    monkeypatch.setattr(repository, "invalidate_dashboard_metrics_cache", lambda: None)
    sample_a = adapter.samples_collection.insert_one({"name": "A", "asp_id": "hema"}).inserted_id
    sample_b = adapter.samples_collection.insert_one({"name": "B", "asp_id": "solid"}).inserted_id
    simple_id = "7_140453136_A_T"
    identity = repository._simple_id_identity_query(simple_id)
    variant_a = adapter.variants_collection.insert_one(
        {
            **identity,
            "SAMPLE_ID": str(sample_a),
            "genes": ["BRAF"],
            "HGVSp": ["p.V600E"],
            "HGVSc": ["c.1799T>A"],
            "variant_class": "SNV",
            "GT": [{"type": "case", "AF": 0.2}],
            "comments": [],
            "fp": False,
        }
    ).inserted_id
    adapter.variants_collection.insert_one(
        {
            **identity,
            "SAMPLE_ID": str(sample_b),
            "genes": ["BRAF"],
            "HGVSp": ["p.V600E"],
            "variant_class": "SNV",
            "GT": [{"type": "case", "AF": 0.7}],
            "fp": True,
            "interesting": True,
        }
    )
    adapter.variants_collection.insert_one(
        {
            **repository._simple_id_identity_query("1_10_G_C"),
            "SAMPLE_ID": str(sample_a),
            "genes": ["TP53"],
            "variant_class": "INDEL",
            "irrelevant": True,
        }
    )

    assert len(list(repository.get_case_variants({"SAMPLE_ID": str(sample_a)}))) == 2
    assert repository.get_variant(str(variant_a))["genes"] == ["BRAF"]
    selected = repository.update_selected_transcript(
        var_id=str(variant_a),
        selected_csq={"Feature": "NM_004333.6"},
        selected_feature="NM_004333.6",
        criteria="ncbi_mane_select",
    )
    assert selected.matched_count == 1
    assert (
        repository.get_variant(str(variant_a))["INFO"]["selected_CSQ_criteria"]
        == "ncbi_mane_select"
    )
    other = repository.get_variant_in_other_samples(repository.get_variant(str(variant_a)))
    assert other[0]["sample_name"] == "B" and other[0]["fp"] is True
    assert len(repository.get_variants_by_identity(simple_id=simple_id, limit=1)) == 1
    assert (
        len(repository.get_variants_by_identity(simple_id=simple_id, sample_id=str(sample_a))) == 1
    )
    assert len(list(repository.get_variants_by_gene("BRAF"))) == 2
    assert (
        len(
            list(
                repository.get_variants_by_gene_plus_variant_list(
                    "BRAF", ["", "p.V600E", simple_id]
                )
            )
        )
        == 2
    )

    repository.mark_false_positive_var(str(variant_a))
    repository.unmark_false_positive_var(str(variant_a))
    repository.mark_false_positive_var_bulk([str(variant_a)])
    repository.unmark_false_positive_var_bulk([str(variant_a)])
    repository.mark_interesting_var(str(variant_a))
    repository.unmark_interesting_var(str(variant_a))
    repository.mark_irrelevant_var(str(variant_a))
    repository.unmark_irrelevant_var(str(variant_a))
    repository.mark_irrelevant_var_bulk([str(variant_a)])
    repository.unmark_irrelevant_var_bulk([str(variant_a)])
    repository.set_override_blacklist(str(variant_a), True)
    comment_id = str(ObjectId())
    repository.add_var_comment(
        str(variant_a), {"_id": ObjectId(comment_id), "text": "variant", "hidden": 0}
    )
    repository.hide_var_comment(str(variant_a), comment_id)
    assert repository.hidden_var_comments(str(variant_a)) is True
    repository.unhide_variant_comment(str(variant_a), comment_id)

    assert repository.get_total_variant_counts() == 3
    assert repository.get_unique_total_variant_counts() == 2
    assert repository.get_total_snp_counts() == 2
    assert repository.get_fp_counts() == 1
    assert repository.get_unique_snp_count() == 1
    assert repository.get_unique_fp_count() == 1
    stats = repository.get_variant_stats(str(sample_a), genes=["BRAF"])
    assert stats["variants"] == 1 and stats["by_variant_class"] == {"SNV": 1}
    assert repository.delete_sample_variants(str(sample_a)).deleted_count == 2


def test_variant_dashboard_metric_cache_persistence_and_expiry(monkeypatch) -> None:
    adapter = _adapter()
    repository = VariantsRepository(adapter)
    simple_id = "1_10_A_T"
    adapter.variants_collection.insert_many(
        [
            {
                **repository._simple_id_identity_query(simple_id),
                "variant_class": "SNV",
                "fp": True,
            },
            {
                **repository._simple_id_identity_query(simple_id),
                "variant_class": "SNV",
            },
        ]
    )
    quality = repository.get_unique_variant_quality_counts()
    assert quality["unique_total_variants"] == 1 and quality["unique_fp_variants"] == 1
    assert repository.get_unique_variant_quality_counts()["unique_total_variants"] == 1
    rollup = repository.get_dashboard_variant_counts()
    assert rollup["total_variants"] == 2 and rollup["by_variant_class"] == {"SNV": 2}
    assert repository.get_dashboard_variant_counts()["total_variants"] == 2

    adapter.app.cache.clear()
    adapter.coyote_db.dashboard_metrics.update_one(
        {"_id": "variant_rollup_v3"},
        {"$set": {"updated_at": datetime.now(timezone.utc) - timedelta(days=2)}},
    )
    assert repository._read_persisted_metric("missing") is None
    assert repository._read_persisted_metric("variant_rollup_v3", max_age_seconds=1) is None
    repository.invalidate_dashboard_metrics_cache()
    assert adapter.coyote_db.dashboard_metrics.count_documents({}) == 0
