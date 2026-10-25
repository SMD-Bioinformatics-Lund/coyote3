"""Exercise private demo installation without network connections or real databases."""

import json
from unittest.mock import Mock

import mongomock
import pytest

from api.infra.mongo.repositories import demo_installation
from api.services.provisioning.demo_installation import BUNDLE, DemoInstallationService
from coyote3.application.ingest.collection_writes import parse_yaml_payload
from coyote3.application.ingest.service import InternalIngestService
from coyote3.contracts.schemas.registry import INGEST_DEPENDENT_COLLECTIONS
from coyote3.domain.exceptions import AppError
from scripts.quality.export_demo_workflows import MemoryGateway, MemoryVault


def test_bootstrap_factory_builds_configurations_without_rule_publications():
    """Fresh bootstrap can prepare ASPCs before any query or reporting sources exist."""
    from scripts.bootstrap.demo_service import build_demo_service

    client = mongomock.MongoClient()
    service = build_demo_service(client.synthetic_application, client.synthetic_knowledgebase)
    documents = service.configuration("synthetic-installer")
    assert documents["asp_configs"]
    assert all(not row.get("query_policy_release") for row in documents["asp_configs"])
    assert all(not row.get("clinical_rule_release") for row in documents["asp_configs"])


@pytest.fixture
def installer(monkeypatch):
    """Bind real configuration validation and repository operations to isolated Mongo doubles."""
    database = mongomock.MongoClient().synthetic
    repository = demo_installation.DemoInstallationRepository(database)
    ingest = Mock()
    ingest.parse_yaml_payload.side_effect = parse_yaml_payload
    monkeypatch.setattr(demo_installation, "run_transaction", lambda client, fn: fn(None))
    monkeypatch.setattr(demo_installation, "enqueue_audit", lambda *args, **kwargs: None)
    service = DemoInstallationService(repository, ingest, identifier_factory=repository.identifier)
    groups = {row["asp_group"] for row in service.configuration("admin")["assay_specific_panels"]}
    database.assay_groups.insert_many([{"group_id": group, "is_active": True} for group in groups])
    database.query_rule_sets.insert_one({"scope_key": "synthetic_baseline"})
    return service, database, ingest


def test_plan_install_and_collision_preserve_existing_configuration(installer):
    service, database, _ = installer
    plan = service.plan()
    assert not plan.configuration_installed
    assert len(plan.samples) == 18
    assert not database.asp_configs.count_documents({})
    service.install_configuration("demo.admin")
    for name in (
        "assay_specific_panels",
        "asp_configs",
        "insilico_genelists",
        "clinical_rule_sets",
        "diagnoses",
        "diagnosis_associations",
    ):
        assert all(row["system_installed"] for row in database[name].find())
    assert service.plan().configuration_installed
    assert {r["environment"] for r in database.asp_configs.find()} == {"testing", "production"}
    assert {r["status"] for r in database.clinical_rule_sets.find()} == {"published"}
    assert all(r["active"] for r in database.clinical_rule_sets.find())
    assert database.clinical_rule_revisions.count_documents({}) == 24
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
    assert payload["asp_id"] == "demo-hematology-training"
    assert payload["diagnosis_id"] == "myeloid"
    assert db.asp_configs.find_one({"asp_id": payload["asp_id"]})["environment"] == "testing"
    assert (
        db.diagnosis_associations.find_one({"asp_id": payload["asp_id"]})["diagnosis_id"]
        == payload["diagnosis_id"]
    )
    assert db.insilico_genelists.find_one({"isgl_id": "myeloid-variants"})["asp_ids"] == [
        payload["asp_id"]
    ]
    rule = db.clinical_rule_sets.find_one({"scope.asp_id": payload["asp_id"]})
    assert rule["active"] and rule["status"] == "published"
    assert rule["scope"]["asp_id"] == payload["asp_id"]
    assert (
        db.query_rule_sets.find_one({"system_installed": True})["scope"]["diagnosis_id"]
        == payload["diagnosis_id"]
    )
    assert db.query_rule_revisions.count_documents({}) == 2
    assert db.public_assay_catalog_versions.find_one()["status"] == "published"
    assert db.public_assay_catalog.count_documents({}) == 1
    catalog = db.public_assay_catalog.find_one()
    offerings = catalog["published_offerings"]
    assert len(offerings) == 15
    assert {row["family"] for row in offerings if row["diagnosis_id"] == "mpn"} == {
        "panel-dna",
        "wgs",
    }
    assert {row["group_id"] for row in offerings} == {"hematology", "solid"}
    assert db.asp_configs.count_documents({"environment": "production"}) == 15
    assert db.public_assay_catalog_revisions.count_documents({}) == 1
    db.samples.insert_one(
        {
            "name": payload["name"],
            "asp_id": payload["asp_id"],
            "environment": "testing",
            "diagnosis_id": payload["diagnosis_id"],
        }
    )
    rna = ingest.ingest_sample_bundle.call_args_list[1].args[0]
    db.samples.insert_one(
        {
            "name": rna["name"],
            "asp_id": rna["asp_id"],
            "diagnosis_id": rna["diagnosis_id"],
            "environment": "testing",
        }
    )
    assert service.install_starter("demo.admin")["status"] == "already_installed"
    assert ingest.ingest_sample_bundle.call_count == 2
    assert db.clinical_rule_sets.count_documents({}) == 24


def test_starter_preserves_existing_public_catalog(installer):
    """A center publication is never replaced by installing demonstration assets."""
    service, db, _ = installer
    db.public_assay_catalog.insert_one({"catalog_id": "default", "header": "Center"})
    service.install_starter("demo.admin")
    assert db.public_assay_catalog.find_one()["header"] == "Center"
    assert db.public_assay_catalog_versions.find_one()["status"] == "draft"


def test_shared_diagnosis_requires_every_assay_association(installer):
    """An existing panel link cannot stand in for the same diagnosis's WGS link."""
    service, database, _ = installer
    service.install_configuration("demo.admin")
    database.diagnosis_associations.delete_one(
        {"diagnosis_id": "mpn", "asp_id": "demo-tumwgs-hema"}
    )
    assert not service.plan().configuration_installed
    service.repository.repair_configuration(service.configuration("demo.admin"), "demo.admin")
    assert service.plan().configuration_installed


def test_bundle_does_not_infer_diagnosis_links_from_gene_list_applicability(installer):
    """Matching ISGL scope cannot silently authorize a diagnosis for another assay."""
    from api.bootstrap.compilation import compile_bundle_configurations

    service, _, _ = installer
    documents = service.configuration("demo.admin")
    documents["diagnosis_associations"] = [
        row
        for row in documents["diagnosis_associations"]
        if (row["asp_id"], row["diagnosis_id"]) != ("demo-tumwgs-hema", "mpn")
    ]
    with pytest.raises(ValueError, match="explicit shared diagnosis"):
        compile_bundle_configurations(documents)


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
        if payload["asp_category"] == "rna":
            raise RuntimeError("RNA ingest failed")
        db.samples.insert_one(
            {
                "name": payload["name"],
                "asp_id": payload["asp_id"],
                "diagnosis_id": payload["diagnosis_id"],
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
        "diagnoses",
        "diagnosis_associations",
        "assay_groups",
        "insilico_genelists",
    }
    service.ingest = InternalIngestService(
        collection_gateway=MemoryGateway(collections={name: db[name] for name in names}),
        anno_vep_repository=MemoryVault(db.anno_vep),
        invalidate_dashboard_metrics=lambda: None,
    )
    service.install_starter("system", created_by="system")
    sample = db.samples.find_one({"name": "DEMO_STARTER_DNA"})
    assert (
        db.asp_configs.find_one({"_id": sample["current_aspc_id"]})["aspc_id"]
        == "demo-hematology-training::myeloid::testing"
    )
    assert sample["diagnosis_id"] == "myeloid"
    assert sample["asp_category"] == "dna"
    assert sample["asp_family"] == "panel-dna"
    assert sample["current_aspc_name"]
    assert sample["aspc_resolution"] == {
        "resolved_diagnosis_id": "myeloid",
        "used_base_configuration": False,
        "warning": None,
    }
    assert not {"current_aspc_key", "current_aspc_version"} & sample.keys()
    assert (
        db.assay_specific_panels.find_one({"asp_id": sample["asp_id"]})["asp_group"] == "hematology"
    )
    rna = db.samples.find_one({"name": "DEMO_STARTER_RNA"})
    assert (
        db.asp_configs.find_one({"_id": rna["current_aspc_id"]})["aspc_id"]
        == "demo-rna-training::lymphoid::testing"
    )
    assert rna["diagnosis_id"] == "lymphoid"
    assert rna["asp_category"] == "rna"
    assert rna["asp_family"] == "panel-rna"
    assert rna["current_aspc_name"]
    assert "context" not in rna["aspc_resolution"]
    assert not {"current_aspc_key", "current_aspc_version"} & rna.keys()
    assert db.assay_specific_panels.find_one({"asp_id": rna["asp_id"]})["asp_group"] == "hematology"
    assert db.fusions.count_documents({"SAMPLE_ID": str(rna["_id"])}) > 0
    assert service.plan().starter_installed
    for name in ("variants", "cnvs", "translocations", "biomarkers"):
        assert db[name].count_documents({"SAMPLE_ID": str(sample["_id"])}) > 0
    from coyote3.application.reporting.clinical_rules.validation import validate_rule_set
    from coyote3.contracts.schemas.clinical_rules import ClinicalRuleSetDoc

    for rule in db.clinical_rule_sets.find():
        result = validate_rule_set(ClinicalRuleSetDoc.model_validate(rule), require_tests=True)
        assert result.valid, result.errors
    assert sample["ingested_by"] == rna["ingested_by"] == "system"
    assert (
        service.install_starter("maintenance.admin", force=True, created_by="system")["status"]
        == "installed"
    )
    assert db.samples.find_one({"name": "DEMO_STARTER_DNA"})["_id"] == sample["_id"]
    assert db.samples.find_one({"name": "DEMO_STARTER_RNA"})["_id"] == rna["_id"]
    assert db.samples.count_documents({}) == 2


def test_starter_collision_never_replaces_center_content(installer):
    service, db, ingest = installer
    original = {"asp_id": "demo-hematology-training", "display_name": "Existing center content"}
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
    assert call.kwargs == {
        "ingested_by": "demo.admin",
        "ingest_source": "api",
        "allow_update": False,
    }
    assert call.args[0]["vcf_files"] == str((BUNDLE / "raw/dna.vcf").resolve())
    database.samples.insert_one({"name": "DEMO_GROUP_DNA", "asp_id": "demo-tumwgs-solid"})
    assert service.install_sample("demo_group_dna", "demo.admin")["status"] == "already_installed"
    assert ingest.ingest_sample_bundle.call_count == 1


def test_configuration_is_validated_before_any_repository_write(installer, tmp_path):
    service, _, _ = installer
    setup = tmp_path / "setup"
    setup.mkdir()
    source = json.loads((BUNDLE / "setup/asp_configs.json").read_text())
    source[0]["environment"] = "development"
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


@pytest.mark.parametrize("protection", ["human", "report", "comment", "rna_classification"])
def test_force_demo_preserves_human_provenance_and_review_artifacts(installer, protection):
    service, database, ingest = installer
    service.install_starter("system", created_by="system")
    sample = {
        "name": "DEMO_STARTER_DNA",
        "asp_id": "demo-hematology-training",
        "diagnosis_id": "myeloid",
        "environment": "testing",
        "ingested_by": "system",
    }
    if protection == "human":
        sample["ingested_by"] = "center.operator"
    elif protection == "report":
        sample["reported"] = True
    database.samples.insert_one(sample)
    if protection == "comment":
        database.sample_comments.insert_one({"sample_oid": sample["_id"], "comment": "Keep"})
    elif protection == "rna_classification":
        database.rna_classification.insert_one({"SAMPLE_ID": str(sample["_id"]), "tier": "I"})
    ingest.ingest_sample_bundle.reset_mock()
    before = database.samples.find_one()
    result = service.install_sample("first_sample", "maintenance.admin", force=True)
    assert result["status"] == "already_installed"
    ingest.ingest_sample_bundle.assert_not_called()
    assert database.samples.find_one() == before


def test_force_demo_restores_missing_setup_without_replacing_rule_history(installer):
    service, database, _ = installer
    service.install_starter("system", created_by="system")
    history = list(database.clinical_rule_revisions.find())
    database.diagnosis_associations.delete_one({"asp_id": "demo-hematology-training"})
    service.install_starter("maintenance.admin", force=True, created_by="system")
    assert (
        database.diagnosis_associations.find_one({"asp_id": "demo-hematology-training"}) is not None
    )
    assert list(database.clinical_rule_revisions.find()) == history


def test_force_demo_still_requires_application_baseline(installer):
    service, database, ingest = installer
    database.assay_groups.delete_many({})
    with pytest.raises(AppError, match="baseline"):
        service.install_starter("maintenance.admin", force=True, created_by="system")
    assert database.asp_configs.count_documents({}) == 0
    ingest.ingest_sample_bundle.assert_not_called()
