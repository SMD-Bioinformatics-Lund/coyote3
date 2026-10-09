"""Exercise portable synthetic evidence against ingest and clinical query contracts."""

import json
from types import SimpleNamespace

import pytest

from api.application.query_rules import QueryRuleService
from api.config.clinical_query_policy import resolved_query_policy
from api.contracts.schemas.query_rules import QueryRuleDraft, QueryRuleScope
from api.domain.core.dna.cnvqueries import build_cnv_query
from api.domain.core.dna.varqueries import build_query
from api.domain.core.rna.fusion_query_builder import build_fusion_query
from api.infra.mongo.repositories.query_rules import QueryRuleRepository
from scripts.quality.export_demo_workflows import ROOT, replay, review_examples


@pytest.fixture(scope="module")
def demo_db():
    """Replay raw fixtures through the real ingest service in isolated memory."""
    return replay()


def test_demo_structural_events_reach_the_collection_with_embedded_evidence(demo_db):
    """Verify the service persists paired BND evidence and symbolic endpoints."""
    pair = demo_db.translocations.find_one({"ID": "custom-left"})
    assert pair is not None
    assert pair["SAMPLE_ID"]
    assert {row["ID"] for row in pair["source_records"]} == {"custom-left", "custom-right"}
    assert pair["INFO"]["ANN"][0]["Gene_Name"] == "KMT2A&NPM1"
    assert demo_db.translocations.find_one({"ID": "custom-right"}) is None
    assert demo_db.translocations.find_one({"ID": "demo-deletion"})["END"] == 51001
    assert demo_db.translocations.find_one({"ID": "demo-duplication"})["END"] == 61001


@pytest.mark.parametrize(
    "name,assay,collection",
    [
        ("DEMO_GROUP_DNA", "demo_e2e_demo_dna", "variants"),
        ("DEMO_GROUP_RNA", "demo_e2e_demo_rna", "fusions"),
    ],
)
def test_demo_group_has_complete_sample_and_reporting_configuration(
    demo_db, name, assay, collection
):
    """Dedicated demo-group samples resolve their own profiles, evidence and report drafts."""
    sample = demo_db.samples.find_one({"name": name})
    assert sample["asp_id"] == assay
    asp = demo_db.assay_specific_panels.find_one({"asp_id": assay})
    assert asp["asp_group"] == "demo"
    aspc = demo_db.asp_configs.find_one({"aspc_id": sample["current_aspc_key"]})
    assert aspc["asp_group"] == "demo"
    assert aspc["environment"] == "testing"
    assert demo_db[collection].count_documents({"SAMPLE_ID": str(sample["_id"])}) > 0
    rule = demo_db.clinical_rule_sets.find_one({"scope.asp_id": assay})
    assert rule["status"] == "draft"
    assert not rule["active"]


def selected_labels(db, name, **overrides):
    """Resolve installed policies and return scenario labels for selected raw SNVs."""
    sample = db.samples.find_one({"name": name})
    asp = db.assay_specific_panels.find_one({"asp_id": sample["asp_id"]})
    service = QueryRuleService(
        QueryRuleRepository(
            SimpleNamespace(
                query_rule_sets_collection=db.query_rule_sets,
                query_rule_revisions_collection=db.query_rule_revisions,
            )
        )
    )
    resolved = service.resolve(
        QueryRuleScope(
            assay_group=asp["asp_group"],
            asp_id=sample["asp_id"],
            subpanel_id=sample["subpanel_id"],
            analysis="snv",
        )
    )
    settings = dict(
        sample["filters"]["somatic"]["snv"],
        id=str(sample["_id"]),
        asp_id=sample["asp_id"],
        subpanel_id=sample["subpanel_id"],
        filter_conseq=["missense_variant"],
    )
    settings.update(overrides)
    query = build_query(
        asp["asp_group"],
        settings,
        policy=resolved_query_policy("snv", resolved.evidence_mode, resolved.exceptions),
    )
    labels = {
        r["simple_id"]: r["id"] for r in json.loads((ROOT / "scenarios/variants.json").read_text())
    }
    return {labels[row["simple_id"]] for row in db.variants.find(query)}


@pytest.mark.parametrize("group", ["HEMATOLOGY", "MYELOID", "TUMWGS", "SOLID", "LYMPHOID"])
def test_raw_variants_cover_installed_rules(demo_db, group):
    """Positive and negative raw evidence distinguishes each installed group policy."""
    selected = selected_labels(demo_db, "DEMO_" + group)
    expected = {
        "baseline_pass",
        "tier2_candidate",
        "tier3_candidate",
        "tier4_candidate",
        "depth_boundary",
        "alt_reads_boundary",
    }
    if group in {"HEMATOLOGY", "MYELOID", "TUMWGS"}:
        expected |= {
            "flt3_svtype",
            "flt3_long_alt",
            "marker_admitted",
            "cebpa_germline",
            "interval_first",
            "interval_last",
        }
    if group == "SOLID":
        expected |= {"tert_regulatory", "nfkbie_binding", "cebpa_germline", "non_cebpa_germline"}
    assert selected == expected


def test_unpaired_and_gene_restrictions(demo_db):
    """Unpaired evidence and sample gene restrictions retain their independent effects."""
    paired = selected_labels(demo_db, "DEMO_MYELOID")
    assert selected_labels(demo_db, "DEMO_MYELOID_FOCUS") == paired
    assert selected_labels(demo_db, "DEMO_MYELOID_UNPAIRED") == paired | {
        "control_high",
        "control_boundary",
    }
    assert selected_labels(demo_db, "DEMO_MYELOID", filter_genes=["FLT3"]) == {
        "tier2_candidate",
        "flt3_svtype",
        "flt3_long_alt",
    }
    assert (
        selected_labels(demo_db, "DEMO_MYELOID", restrict_to_genes=True, filter_genes=[]) == set()
    )


def test_other_analysis_and_missing_measurement_fixtures(demo_db):
    """Verify counts, optional missing analyses and threshold-selectable CNV/RNA evidence."""
    dna = demo_db.samples.find_one({"name": "DEMO_MYELOID"})
    assert (
        demo_db.cnvs.count_documents(
            build_cnv_query(str(dna["_id"]), dna["filters"]["somatic"]["cnv"])
        )
        == 2
    )
    missing = demo_db.samples.find_one({"name": "DEMO_MYELOID_MISSING"})
    assert missing["ingest_status"] == "ready"
    assert set(missing["missing_expected_files"]) == {"biomarkers"}
    assert not demo_db.biomarkers.count_documents({"SAMPLE_ID": str(missing["_id"])})
    for name in ("DEMO_FUSION", "DEMO_WTS"):
        rna = demo_db.samples.find_one({"name": name})
        settings = dict(rna["filters"]["somatic"]["fusion"], id=str(rna["_id"]))
        assert demo_db.fusions.count_documents(build_fusion_query("fusion", settings)) == 2
        settings.update(min_spanning_reads=10, min_spanning_pairs=5)
        assert demo_db.fusions.count_documents(build_fusion_query("fusion", settings)) == 1
        assert not demo_db.variants.count_documents({"SAMPLE_ID": str(rna["_id"])})


def test_review_examples_preserve_tier_and_measurement_rendering():
    """Tier IV has no tier I–III narrative; absent measurements produce no text."""
    db = replay()
    previews = review_examples(db)
    assert previews == json.loads((ROOT / "expected/report_previews.json").read_text())
    sections = previews["DEMO_MYELOID"]["sections"]
    assert len(sections["Reportable SNVs and small INDELs"]) == 3
    assert not any("NFKBIE" in text for lines in sections.values() for text in lines)
    missing = previews["DEMO_MYELOID_MISSING"]["sections"]
    assert not {"Synthetic HRD", "Synthetic MSI", "Synthetic TMB"} & set(missing)
    assert {row["class"] for row in db.annotation.find()} == {1, 2, 3, 4}
    assert db.finding_comments.count_documents({}) == 12
    assert db.sample_comments.count_documents({"hidden": True}) == 6


def test_query_draft_examples_use_current_contract():
    """The inheritance and nested-condition recipes remain valid editor requests."""
    for row in json.loads((ROOT / "scenarios/query_drafts.json").read_text()):
        QueryRuleDraft.model_validate(row["request"])


def test_report_drafts_have_passing_embedded_cases():
    """The supplied drafts satisfy submission-time validation, including embedded cases."""
    from api.application.reporting.clinical_rules.validation import validate_rule_set
    from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc

    for row in json.loads((ROOT / "setup/clinical_rule_sets.json").read_text()):
        result = validate_rule_set(ClinicalRuleSetDoc.model_validate(row), require_tests=True)
        assert result.valid, result.errors


@pytest.mark.parametrize(
    "uri,database",
    [
        ("mongodb://remote.example:27017", "coyote3_demo"),
        ("mongodb://localhost:27017", "coyote3_smd_prod"),
        ("mongodb://localhost:27017,remote.example:27017", "coyote3_demo"),
    ],
)
def test_demo_installer_rejects_non_demo_targets(uri, database):
    """The reusable setup loader cannot select an ordinary or remote database."""
    from scripts.bootstrap.install_demo_workflows import validate_target

    with pytest.raises(ValueError):
        validate_target(uri, database)


@pytest.mark.parametrize(
    "filename", ["missing_required_file.yaml", "missing_aspc.yaml", "rna_with_snv.yaml"]
)
def test_negative_manifests_reject_before_writes(filename):
    """Invalid fixture resources and scopes fail before sample/dependent insertion."""
    from api.application.ingest.service import InternalIngestService
    from api.config.constants import ALL_SAMPLE_FILE_KEYS
    from scripts.quality.export_demo_workflows import MemoryGateway, MemoryVault

    db = replay()
    names = set(db.list_collection_names()) | {"hgnc_genes"}
    service = InternalIngestService(
        collection_gateway=MemoryGateway(collections={name: db[name] for name in names}),
        anno_vep_repository=MemoryVault(db.anno_vep),
        invalidate_dashboard_metrics=lambda: None,
    )
    path = ROOT / "negative" / filename
    payload = service.parse_yaml_payload(path.read_text())
    for key in ALL_SAMPLE_FILE_KEYS:
        if payload.get(key):
            payload[key] = str((path.parent / payload[key]).resolve())
    counts = {name: db[name].count_documents({}) for name in names}
    with pytest.raises((ValueError, FileNotFoundError)):
        service.ingest_sample_bundle(payload, ingested_by="demo.ingester", ingest_source="api")
    assert counts == {name: db[name].count_documents({}) for name in names}
