"""Exercise private demo installation without network connections or real databases."""

import json
from unittest.mock import Mock

import mongomock
import pytest

from api.application.demo_installation import BUNDLE, DemoInstallationService
from api.application.ingest.collection_writes import parse_yaml_payload
from api.domain.core.exceptions import AppError
from api.infra.mongo.repositories import demo_installation


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
    assert service.plan().configuration_installed
    assert {r["environment"] for r in database.asp_configs.find()} == {"testing"}
    assert {r["status"] for r in database.clinical_rule_sets.find()} == {"draft"}
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


def test_drafts_are_validated_before_any_repository_write(installer, tmp_path):
    service, _, _ = installer
    setup = tmp_path / "setup"
    setup.mkdir()
    source = json.loads((BUNDLE / "setup/asp_configs.json").read_text())
    source[0]["environment"] = "production"
    (setup / "asp_configs.json").write_text(json.dumps(source))
    service.bundle = tmp_path
    with pytest.raises(AppError, match="testing"):
        service.install_configuration("admin")
