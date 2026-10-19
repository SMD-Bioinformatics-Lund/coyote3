"""Exercise private demo installation without network connections or real databases."""

import json
from unittest.mock import Mock

import mongomock
import pytest

from api.application.demo_installation import BUNDLE, DemoInstallationService
from api.application.ingest.collection_writes import parse_yaml_payload
from api.application.ingest.service import InternalIngestService
from api.contracts.schemas.registry import INGEST_DEPENDENT_COLLECTIONS
from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories import demo_installation
from scripts.quality.export_demo_workflows import MemoryGateway, MemoryVault


@pytest.fixture
def installer(monkeypatch):
    """Bind real configuration validation and repository operations to isolated Mongo doubles."""
    database = mongomock.MongoClient().synthetic
    repository = demo_installation.DemoInstallationRepository(database)
    ingest = Mock()
    ingest.parse_yaml_payload.side_effect = parse_yaml_payload
    monkeypatch.setattr(demo_installation, "run_transaction", lambda client, fn: fn(None))
    monkeypatch.setattr(demo_installation, "enqueue_audit", lambda *args, **kwargs: None)
    service = DemoInstallationService(repository, ingest)
    groups = {row["asp_group"] for row in service.configuration("admin")["assay_specific_panels"]}
    database.assay_groups.insert_many([{"group_id": group, "is_active": True} for group in groups])
    database.query_rule_sets.insert_one({"scope_key": "synthetic_baseline"})
    return service, database, ingest


def test_plan_install_and_collision_preserve_existing_configuration(installer):
    service, database, _ = installer
    plan = service.plan()
    assert not plan.configuration_installed
    assert len(plan.samples) == 12
    assert not database.asp_configs.count_documents({})
    service.install_configuration("demo.admin")
    for name in (
        "assay_specific_panels",
        "asp_configs",
        "insilico_genelists",
        "clinical_rule_sets",
        "subpanels",
        "subpanel_associations",
    ):
        assert all(row["system_installed"] for row in database[name].find())
    assert service.plan().configuration_installed
    assert {r["environment"] for r in database.asp_configs.find()} == {"testing"}
    assert {r["status"] for r in database.clinical_rule_sets.find()} == {"published"}
    assert all(r["active"] for r in database.clinical_rule_sets.find())
    assert database.clinical_rule_revisions.count_documents({}) == 9
    before = list(database.asp_configs.find())
    with pytest.raises(AppError, match="already exists"):
        service.install_configuration("other.admin")
    assert list(database.asp_configs.find()) == before


def test_prerequisites_and_manifest_allowlist(installer):
    service, _, ingest = installer
    with pytest.raises(AppError, match="Unknown"):
        service.install_sample("../../private", "admin")
    with pytest.raises(AppError, match="configuration"):
        service.install_sample("demo_group_dna", "admin")
    ingest.ingest_sample_bundle.assert_not_called()


def test_starter_links_all_resources_and_ingests_first_sample(installer):
    service, db, ingest = installer
    assert service.install_starter("demo.admin")["status"] == "installed"
    payload = ingest.ingest_sample_bundle.call_args_list[0].args[0]
    assert payload["name"] == "DEMO_STARTER_DNA"
    assert payload["asp_id"] == "demo_starter_dna"
    assert payload["subpanel_id"] == "demo_starter_focus"
    assert db.asp_configs.find_one({"asp_id": payload["asp_id"]})["environment"] == "testing"
    assert (
        db.subpanel_associations.find_one({"asp_id": payload["asp_id"]})["subpanel_id"]
        == payload["subpanel_id"]
    )
    assert db.insilico_genelists.find_one()["asp_ids"] == [payload["asp_id"]]
    rule = db.clinical_rule_sets.find_one()
    assert rule["active"] and rule["status"] == "published"
    assert rule["scope"]["asp_id"] == payload["asp_id"]
    assert (
        db.query_rule_sets.find_one({"system_installed": True})["scope"]["subpanel_id"]
        == payload["subpanel_id"]
    )
    assert db.query_rule_revisions.count_documents({}) == 2
    assert db.public_assay_catalog_versions.find_one()["status"] == "published"
    assert db.public_assay_catalog.count_documents({}) == 1
    catalog = db.public_assay_catalog.find_one()
    assert catalog["modalities"]["dna"]["categories"]["starter"]["analysis"] == ["SNV", "CNV"]
    assert catalog["modalities"]["dna"]["categories"]["focus"]["analysis"] == ["SNV"]
    assert catalog["modalities"]["rna"]["categories"]["fusion"]["analysis"] == ["FUSION"]
    assert db.asp_configs.count_documents({"environment": "production"}) == 2
    assert db.public_assay_catalog_revisions.count_documents({}) == 1
    db.samples.insert_one(
        {
            "name": payload["name"],
            "asp_id": payload["asp_id"],
            "environment": "testing",
            "subpanel_id": payload["subpanel_id"],
        }
    )
    rna = ingest.ingest_sample_bundle.call_args_list[1].args[0]
    db.samples.insert_one(
        {
            "name": rna["name"],
            "asp_id": rna["asp_id"],
            "subpanel_id": rna["subpanel_id"],
            "environment": "testing",
        }
    )
    assert service.install_starter("demo.admin")["status"] == "already_installed"
    assert ingest.ingest_sample_bundle.call_count == 2
    assert db.clinical_rule_sets.count_documents({}) == 2


def test_starter_preserves_existing_public_catalog(installer):
    """A center publication is never replaced by installing demonstration assets."""
    service, db, _ = installer
    db.public_assay_catalog.insert_one({"catalog_id": "default", "header": "Center"})
    service.install_starter("demo.admin")
    assert db.public_assay_catalog.find_one()["header"] == "Center"
    assert db.public_assay_catalog_versions.find_one()["status"] == "draft"


def test_starter_retry_after_ingest_failure_preserves_configuration(installer):
    service, db, ingest = installer
    ingest.ingest_sample_bundle.side_effect = RuntimeError("Synthetic parser failure")
    with pytest.raises(RuntimeError, match="parser failure"):
        service.install_starter("demo.admin")
    identifiers = list(db.assay_specific_panels.find({}, {"_id": 1}))
    ingest.ingest_sample_bundle.side_effect = None
    service.install_starter("demo.admin")
    assert list(db.assay_specific_panels.find({}, {"_id": 1})) == identifiers


def test_starter_retry_skips_completed_dna_when_rna_failed(installer):
    service, db, ingest = installer

    def ingest_once(payload, **kwargs):
        if payload["omics_layer"] == "rna":
            raise RuntimeError("RNA ingest failed")
        db.samples.insert_one(
            {
                "name": payload["name"],
                "asp_id": payload["asp_id"],
                "subpanel_id": payload["subpanel_id"],
                "environment": "testing",
            }
        )

    ingest.ingest_sample_bundle.side_effect = ingest_once
    with pytest.raises(RuntimeError, match="RNA ingest failed"):
        service.install_starter("demo.admin")
    plan = service.plan()
    assert [sample.installed for sample in plan.starter_samples] == [True, False]
    assert not plan.starter_installed
    ingest.ingest_sample_bundle.reset_mock()
    ingest.ingest_sample_bundle.side_effect = None
    service.install_starter("demo.admin")
    assert ingest.ingest_sample_bundle.call_count == 1
    assert ingest.ingest_sample_bundle.call_args.args[0]["name"] == "DEMO_STARTER_RNA"


def test_starter_first_sample_uses_real_ingest(installer):
    service, db, _ = installer
    names = set(INGEST_DEPENDENT_COLLECTIONS.values()) | {
        "samples",
        "anno_vep",
        "hgnc_genes",
        "asp_configs",
        "assay_specific_panels",
        "subpanels",
        "subpanel_associations",
        "assay_groups",
        "insilico_genelists",
    }
    service.ingest = InternalIngestService(
        collection_gateway=MemoryGateway(collections={name: db[name] for name in names}),
        anno_vep_repository=MemoryVault(db.anno_vep),
        invalidate_dashboard_metrics=lambda: None,
    )
    service.install_starter("demo.admin")
    sample = db.samples.find_one({"name": "DEMO_STARTER_DNA"})
    assert sample["current_aspc_key"] == "demo_starter_dna_focus_testing"
    assert sample["subpanel_id"] == "demo_starter_focus"
    assert (
        db.assay_specific_panels.find_one({"asp_id": sample["asp_id"]})["asp_group"] == "hematology"
    )
    rna = db.samples.find_one({"name": "DEMO_STARTER_RNA"})
    assert rna["current_aspc_key"] == "demo_starter_rna_fusion_testing"
    assert rna["subpanel_id"] == "demo_starter_fusion"
    assert db.assay_specific_panels.find_one({"asp_id": rna["asp_id"]})["asp_group"] == "fusion"
    assert db.fusions.count_documents({"SAMPLE_ID": str(rna["_id"])}) > 0
    assert service.plan().starter_installed
    for name in ("variants", "cnvs", "translocations", "biomarkers"):
        assert db[name].count_documents({"SAMPLE_ID": str(sample["_id"])}) > 0
    from api.application.reporting.clinical_rules.validation import validate_rule_set
    from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc

    for rule in db.clinical_rule_sets.find():
        result = validate_rule_set(ClinicalRuleSetDoc.model_validate(rule), require_tests=True)
        assert result.valid, result.errors


def test_starter_collision_never_replaces_center_content(installer):
    service, db, ingest = installer
    original = {"asp_id": "demo_starter_dna", "display_name": "Existing center content"}
    db.assay_specific_panels.insert_one(original)
    with pytest.raises(AppError, match="already exists"):
        service.install_starter("demo.admin")
    assert db.assay_specific_panels.find_one()["display_name"] == "Existing center content"
    assert db.asp_configs.count_documents({}) == 0
    ingest.ingest_sample_bundle.assert_not_called()


def test_demo_samples_use_normal_ingest_and_never_update_existing(installer):
    service, database, ingest = installer
    service.install_configuration("demo.admin")
    service.install_sample("demo_group_dna", "demo.admin")
    call = ingest.ingest_sample_bundle.call_args
    assert call.kwargs == {"ingested_by": "demo.admin", "ingest_source": "api"}
    assert call.args[0]["vcf_files"] == str(BUNDLE / "raw/dna.vcf")
    database.samples.insert_one({"name": "DEMO_GROUP_DNA", "asp_id": "demo_e2e_demo_dna"})
    assert service.install_sample("demo_group_dna", "demo.admin")["status"] == "already_installed"
    assert ingest.ingest_sample_bundle.call_count == 1


def test_configuration_is_validated_before_any_repository_write(installer, tmp_path):
    service, _, _ = installer
    setup = tmp_path / "setup"
    setup.mkdir()
    source = json.loads((BUNDLE / "setup/asp_configs.json").read_text())
    source[0]["environment"] = "production"
    (setup / "asp_configs.json").write_text(json.dumps(source))
    service.bundle = tmp_path
    with pytest.raises(AppError, match="testing"):
        service.install_configuration("admin")


def test_published_demo_rules_cannot_target_other_assays(installer, tmp_path):
    """Reject published examples outside the assays owned by the demo bundle."""
    service, database, _ = installer
    setup = tmp_path / "setup"
    setup.mkdir()
    (setup / "assay_specific_panels.json").write_text(
        (BUNDLE / "setup/assay_specific_panels.json").read_text()
    )
    rules = json.loads((BUNDLE / "setup/clinical_rule_sets.json").read_text())
    rules[0]["scope"]["asp_id"] = "other_assay"
    rules[0]["rule_set_id"] = "other_assay__base__en"
    (setup / "clinical_rule_sets.json").write_text(json.dumps(rules))
    service.bundle = tmp_path
    with pytest.raises(AppError, match="packaged assay"):
        service.install_configuration("admin")
    assert database.clinical_rule_sets.count_documents({}) == 0
