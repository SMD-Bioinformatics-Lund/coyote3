"""Independent measurement selection, ingestion, rules, snapshots, and migration."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import mongomock
import pytest
from pydantic import ValidationError

from api.application.biomarker.biomarker_lookup import BiomarkerService
from api.application.ingest.dependent_writes import data_counts, replace_dependents
from api.application.ingest.file_policy import validate_payload_file_keys
from api.application.ingest.parsers import DnaIngestParser
from api.application.reporting.clinical_rules.evaluator import condition_matches
from api.application.reporting.clinical_rules.preparation import prepare_report_context
from api.application.reporting.clinical_rules.registry import validate_fact_path
from api.application.reporting.report_renderer import render_report_html
from api.application.reporting.snapshot_rows import build_biomarker_snapshot_rows
from api.config.constants import analysis_file_keys
from api.contracts.schemas.clinical_rules import ClinicalRulePredicate
from api.contracts.schemas.dna import BiomarkersDoc
from api.contracts.schemas.samples import SamplesDoc
from api.domain.common.biomarkers import project_biomarkers
from api.domain.core.exceptions import AppError
from api.infra.mongo.ingest_gateway import IngestCollectionGateway
from scripts.upgrade_from_v3.migrate_biomarker_analyses import (
    migrate,
    requires_rule_review,
    transform_configuration,
)

MEASUREMENTS = {
    "name": "SYNTHETIC-T",
    "HRD": {"tai": 2, "hrd": 3, "lst": 4, "sum": 9},
    "MSIS": {"tot": 100, "som": 0, "per": 0.0},
    "MSIP": {"tot": 100, "som": 1, "per": 1.0},
    "TMB": {"value": 0.0, "unit": "mut/Mb"},
}


@pytest.mark.parametrize(
    "expression",
    [
        {"analysis_declarations": {"BIOMARKER": {}}},
        {"analysis": "LOH"},
        {"evaluation": {"collection": "biomarkers"}},
        {"condition": {"fact": "aggregates.biomarker_count"}},
    ],
)
def test_migration_flags_obsolete_rule_resources(expression):
    """Existing aggregate rules require reviewed replacement releases."""
    assert requires_rule_review({"blocks": [expression]})
    assert not requires_rule_review({"analysis": "MSI", "collection": "msi"})


@pytest.mark.parametrize("collection", ["biomarkers", "loh"])
def test_generic_and_unimplemented_rule_collections_are_rejected(collection):
    """Current rule expressions accept individual supported analyses only."""
    from api.contracts.schemas.clinical_rules import ClinicalRuleEvaluationScope

    with pytest.raises(ValidationError):
        ClinicalRuleEvaluationScope.model_validate({"mode": "each_item", "collection": collection})
    assert ClinicalRuleEvaluationScope(mode="each_item", collection="msi").collection == "msi"


@pytest.mark.parametrize("analysis", ["HRD", "MSI", "TMB"])
def test_shared_file_preserves_independent_measurement_availability(tmp_path, analysis):
    """A file containing one analysis does not make other measurements available."""
    source = tmp_path / "measurements.json"
    expected = project_biomarkers([MEASUREMENTS], [analysis])[0]
    source.write_text(json.dumps(expected))
    key = analysis_file_keys("dna", analysis)[0]
    assert key == "biomarkers"
    payload = DnaIngestParser().parse({"files": {key: {"path": str(source)}}})
    assert payload["biomarkers"] == expected
    BiomarkersDoc.model_validate({**expected, "SAMPLE_ID": "sample"})
    assert data_counts(payload)[analysis.lower()] == 1
    assert all(
        data_counts(payload).get(other.lower(), 0) == 0
        for other in ("HRD", "MSI", "TMB")
        if other != analysis
    )
    rows = build_biomarker_snapshot_rows([expected])
    assert [row["analysis_type"] for row in rows] == [analysis]
    assert rows[0]["simple_id"].startswith(analysis.lower() + ":")


def test_missing_measurement_is_not_a_zero_result(tmp_path):
    source = tmp_path / "empty.json"
    source.write_text(json.dumps({"name": "SYNTHETIC-T", "TMB": None}))
    with pytest.raises(ValueError, match="requires a measurement"):
        DnaIngestParser().parse({"files": {"biomarkers": {"path": str(source)}}})
    assert project_biomarkers([MEASUREMENTS], []) == []
    assert project_biomarkers([MEASUREMENTS], ["TMB"])[0]["TMB"]["value"] == 0


def test_combined_measurements_are_read_once(tmp_path, monkeypatch):
    """One input read retains all supplied analyses, including measured zero."""
    from api.application.ingest import analysis_parsers

    source = tmp_path / "combined.json"
    source.write_text(json.dumps(MEASUREMENTS))
    original = analysis_parsers.read_ingest_json
    calls = []

    def read(path, label):
        calls.append(path)
        return original(path, label)

    monkeypatch.setattr(analysis_parsers, "read_ingest_json", read)
    payload = DnaIngestParser().parse({"biomarkers": str(source)})
    assert calls == [str(source)]
    assert payload["biomarkers"] == MEASUREMENTS
    assert {key: data_counts(payload)[key] for key in ("hrd", "msi", "tmb")} == {
        "hrd": 1,
        "msi": 1,
        "tmb": 1,
    }


@pytest.mark.parametrize("key", ["hrd", "msi", "tmb"])
@pytest.mark.parametrize("container", [None, "files", "_runtime_files"])
def test_separate_file_keys_are_rejected_before_parsing(key, container):
    payload = {key: "synthetic.json"}
    if container:
        payload = {container: payload}
    with pytest.raises(ValueError, match="Use one biomarkers JSON"):
        validate_payload_file_keys(Mock(), {"omics_layer": "dna", **payload})
    if container is None:
        with pytest.raises(ValidationError, match="Use one biomarkers JSON"):
            SamplesDoc.model_validate(payload)


@pytest.mark.parametrize("document", [[], {}, {"HRD": {}}, {"name": "DEMO"}])
def test_invalid_shared_measurement_roots_fail(tmp_path, document):
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="Biomarkers JSON requires"):
        DnaIngestParser().parse({"biomarkers": str(source)})


def test_migration_refuses_distinct_measurement_file_references():
    db = mongomock.MongoClient().test
    db.samples.insert_one({"files": {"hrd": {"path": "a.json"}, "msi": {"path": "b.json"}}})
    original = db.samples.find_one()
    with pytest.raises(ValueError, match="Combine distinct"):
        migrate(db, analyses=["HRD", "MSI"], apply=True)
    assert db.samples.find_one() == original


@pytest.mark.parametrize("field,value", [("TMB", -1), ("TMB", float("inf"))])
def test_invalid_numeric_measurements_are_rejected(field, value):
    with pytest.raises(ValidationError):
        BiomarkersDoc.model_validate(
            {"name": "synthetic", "SAMPLE_ID": "sample", field: {"value": value}}
        )


def test_update_preserves_other_analyses_and_replaces_both_msi_methods():
    """Updating MSI drops its absent paired method but preserves HRD/TMB."""
    existing = {**deepcopy(MEASUREMENTS), "_id": "row", "SAMPLE_ID": "sample"}
    collection = SimpleNamespace(find=Mock(return_value=[existing]), delete_many=Mock())
    writer = Mock(return_value={"biomarkers": 1})
    service = SimpleNamespace(
        _collection=lambda name: collection,
        _write_dependents=writer,
        collection_gateway=IngestCollectionGateway(collections={"biomarkers": collection}),
    )
    preload = {"biomarkers": {"name": "SYNTHETIC-T", "MSIS": {"tot": 10, "som": 1, "per": 10}}}
    replace_dependents(
        service,
        preload=preload,
        sample_id="sample",
        sample_name="SYNTHETIC-T",
        session="transaction",
    )
    merged = writer.call_args.kwargs["preload"]["biomarkers"]
    assert "MSIP" not in merged
    assert merged["HRD"] == MEASUREMENTS["HRD"]
    assert merged["TMB"] == MEASUREMENTS["TMB"]
    assert writer.call_args.kwargs["session"] == "transaction"
    collection.find.assert_called_once_with({"SAMPLE_ID": "sample"}, session="transaction")
    assert existing["MSIP"] == MEASUREMENTS["MSIP"]


@pytest.mark.parametrize(
    "existing",
    [
        [{**MEASUREMENTS, "name": "different-source"}],
        [MEASUREMENTS, MEASUREMENTS],
    ],
)
def test_ambiguous_source_is_rejected_before_replacing_measurements(existing):
    collection = SimpleNamespace(find=Mock(return_value=existing), delete_many=Mock())
    service = SimpleNamespace(
        _collection=lambda name: collection,
        _write_dependents=Mock(),
        collection_gateway=IngestCollectionGateway(collections={"biomarkers": collection}),
    )
    with pytest.raises(ValueError):
        replace_dependents(
            service,
            preload={"biomarkers": MEASUREMENTS},
            sample_id="sample",
            sample_name="synthetic",
            session="transaction",
        )
    collection.delete_many.assert_not_called()
    service._write_dependents.assert_not_called()


def test_rule_facts_respect_report_selection_and_keep_zero():
    context = prepare_report_context(
        sample={"name": "synthetic", "asp_id": "assay"},
        asp={},
        aspc={"reporting": {"report_sections": ["MSI", "TMB"]}},
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={"biomarkers": [MEASUREMENTS]},
    )
    assert context.hrd == []
    assert [row.method for row in context.msi] == ["MSIS", "MSIP"]
    assert context.tmb[0].value == 0
    validate_fact_path("item.value", scope="each_item")
    condition = ClinicalRulePredicate(type="predicate", fact="item.value", operator="eq", value=0)
    assert condition_matches(
        condition, context.evaluation_scope(item=context.tmb[0].model_dump())
    ) == (True, [])


def test_api_selection_uses_stored_configuration(monkeypatch):
    monkeypatch.setattr(
        "api.application.biomarker.biomarker_lookup.get_formatted_assay_config",
        lambda *args, **kwargs: {"analysis_types": ["TMB"]},
    )
    service = BiomarkerService(
        biomarker_repository=SimpleNamespace(get_sample_biomarkers=lambda **kwargs: [MEASUREMENTS]),
        assay_panel_repository=object(),
        assay_configuration_repository=object(),
    )
    sample = {"_id": "sample", "omics_layer": "dna"}
    payload = service.list_payload(sample=sample, analysis_type="TMB")
    assert set(payload["tmb"][0]) == {"name", "TMB"}
    with pytest.raises(AppError):
        service.list_payload(sample=sample, analysis_type="HRD")
    with pytest.raises(AppError):
        service.list_payload(sample=sample, analysis_type="BIOMARKER")
    with pytest.raises(AppError):
        service.list_payload(sample=sample, analysis_type="LOH")


def test_migration_requires_explicit_selection_and_preserves_history():
    original = {
        "analysis_types": ["SNV", "BIOMARKER", "TMB"],
        "reporting": {"report_sections": ["BIOMARKER"]},
        "expected_files": ["biomarkers"],
    }
    updated = transform_configuration(original, ["HRD", "MSI"])
    assert updated["analysis_types"] == ["SNV", "HRD", "MSI", "TMB"]
    assert updated["expected_files"] == ["biomarkers"]
    assert original["expected_files"] == ["biomarkers"]
    db = mongomock.MongoClient().test
    db.asp_configs.insert_one({**original, "asp_id": "assay"})
    db.assay_specific_panels.insert_one(
        {"asp_id": "assay", "expected_files": ["biomarkers", "tmb"]}
    )
    db.reports.insert_one({"report_sections": ["BIOMARKER"]})
    db.clinical_rule_sets.insert_one(
        {
            "active": True,
            "status": "published",
            "analysis_declarations": {"BIOMARKER": {"narrative": "enabled"}},
        }
    )
    assert migrate(db, analyses=["HRD", "MSI"])["rules_requiring_review"] == 1
    with pytest.raises(ValueError, match="Publish reviewed"):
        migrate(db, analyses=["HRD", "MSI"], apply=True)
    assert db.asp_configs.find_one()["analysis_types"] == original["analysis_types"]
    assert db.reports.find_one()["report_sections"] == ["BIOMARKER"]


def test_report_renders_only_selected_measurement_table():
    """Unselected stored values cannot leak into the rendered report body."""
    html = render_report_html(
        template_name="dna_report.html",
        analyte="dna",
        preview=True,
        snapshot_rows=[],
        template_context={
            "sample": {"name": "synthetic", "case": {}, "control": {}},
            "assay_config": {"reporting": {}},
            "report_sections": ["TMB"],
            "report_sections_data": {
                "tmb": project_biomarkers([MEASUREMENTS], ["TMB"]),
                "hrd": project_biomarkers([MEASUREMENTS], ["HRD"]),
            },
            "genes_covered_in_panel": {},
        },
    )
    assert ">TMB</span>" in html
    assert ">HRD</span>" not in html
    assert "mut/Mb" in html
    assert "'value':" not in html


def test_migration_applies_configuration_but_not_saved_evidence(monkeypatch):
    """Applying twice is idempotent and leaves source records and reports unchanged."""
    monkeypatch.setattr(
        "scripts.upgrade_from_v3.migrate_biomarker_analyses.run_transaction",
        lambda client, write: write(None),
    )
    db = mongomock.MongoClient().test
    db.asp_configs.insert_one({"asp_id": "assay", "analysis_types": ["BIOMARKER"]})
    db.assay_specific_panels.insert_one({"asp_id": "assay", "expected_files": ["biomarkers"]})
    db.samples.insert_one(
        {"_id": "sample", "files": {"biomarkers": {"path": "/synthetic/results.json"}}}
    )
    db.biomarkers.insert_one({**MEASUREMENTS, "SAMPLE_ID": "sample"})
    original = db.biomarkers.find_one()
    db.reports.insert_one({"report_sections": ["BIOMARKER"]})
    assert migrate(db, analyses=["HRD", "MSI"], apply=True)["samples"] == 1
    assert db.asp_configs.find_one()["analysis_types"] == ["HRD", "MSI"]
    assert set(db.samples.find_one()["files"]) == {"biomarkers"}
    assert db.biomarkers.find_one() == original
    assert db.reports.find_one()["report_sections"] == ["BIOMARKER"]
    assert migrate(db, analyses=["HRD", "MSI"], apply=True)["samples"] == 0
