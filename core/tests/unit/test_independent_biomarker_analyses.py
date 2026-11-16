"""Independent measurement selection, ingestion, rules, snapshots, and migration."""

import json
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from core_test_support.measurements import MEASUREMENTS
from coyote.application.biomarker.biomarker_lookup import BiomarkerService
from coyote.application.ingest.analysis_parsers import DnaIngestParser
from coyote.application.ingest.dependent_writes import data_counts
from coyote.application.ingest.file_policy import validate_payload_file_keys
from coyote.application.reporting.clinical_rules.evaluator import condition_matches
from coyote.application.reporting.clinical_rules.preparation import prepare_report_context
from coyote.application.reporting.clinical_rules.registry import validate_fact_path
from coyote.application.reporting.report_renderer import render_report_html
from coyote.application.reporting.snapshot_rows import build_biomarker_snapshot_rows
from coyote.config.constants import analysis_file_keys
from coyote.contracts.schemas.clinical_rules import ClinicalRulePredicate
from coyote.contracts.schemas.dna import BiomarkersDoc
from coyote.contracts.schemas.samples import SamplesDoc
from coyote.domain.common.biomarkers import project_biomarkers
from coyote.domain.exceptions import AppError
from pydantic import ValidationError


@pytest.mark.parametrize("collection", ["biomarkers", "loh"])
def test_generic_and_unimplemented_rule_collections_are_rejected(collection):
    """Current rule expressions accept individual supported analyses only."""
    from coyote.contracts.schemas.clinical_rules import ClinicalRuleEvaluationScope

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
    from coyote.application.ingest import analysis_parsers

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


@pytest.mark.parametrize("field", ["clinical_assessment", "assessment_history"])
def test_ingest_cannot_supply_manual_review_metadata(tmp_path, field):
    document = deepcopy(MEASUREMENTS)
    document["HRD"][field] = {"value": "HIGH", "assessed_by": "forged"}
    source = tmp_path / "measurements.json"
    source.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="review workflow"):
        DnaIngestParser().parse({"biomarkers": str(source)})


@pytest.mark.parametrize("key", ["hrd", "msi", "tmb"])
@pytest.mark.parametrize("container", [None, "files", "_runtime_files"])
def test_separate_file_keys_are_rejected_before_parsing(key, container):
    payload = {key: "synthetic.json"}
    if container:
        payload = {container: payload}
    with pytest.raises(ValueError, match="Use one biomarkers JSON"):
        validate_payload_file_keys(Mock(), {"asp_category": "dna", **payload})
    if container is None:
        with pytest.raises(ValidationError, match="Use one biomarkers JSON"):
            SamplesDoc.model_validate(payload)


@pytest.mark.parametrize("document", [[], {}, {"HRD": {}}, {"name": "DEMO"}])
def test_invalid_shared_measurement_roots_fail(tmp_path, document):
    source = tmp_path / "invalid.json"
    source.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="Biomarkers JSON requires"):
        DnaIngestParser().parse({"biomarkers": str(source)})


@pytest.mark.parametrize("field,value", [("TMB", -1), ("TMB", float("inf"))])
def test_invalid_numeric_measurements_are_rejected(field, value):
    with pytest.raises(ValidationError):
        BiomarkersDoc.model_validate(
            {"name": "synthetic", "SAMPLE_ID": "sample", field: {"value": value}}
        )


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
        "coyote.application.biomarker.biomarker_lookup.get_formatted_assay_config",
        lambda *args, **kwargs: {"analysis_types": ["TMB"]},
    )
    service = BiomarkerService(
        biomarker_repository=SimpleNamespace(get_sample_biomarkers=lambda **kwargs: [MEASUREMENTS]),
        assay_panel_repository=object(),
        assay_configuration_repository=object(),
    )
    sample = {"_id": "sample", "asp_category": "dna"}
    payload = service.list_payload(sample=sample, analysis_type="TMB")
    assert set(payload["tmb"][0]) == {"name", "TMB"}
    with pytest.raises(AppError):
        service.list_payload(sample=sample, analysis_type="HRD")
    with pytest.raises(AppError):
        service.list_payload(sample=sample, analysis_type="BIOMARKER")
    with pytest.raises(AppError):
        service.list_payload(sample=sample, analysis_type="LOH")


def test_report_renders_only_selected_measurement_table():
    """Unselected stored values cannot leak into the rendered report body."""
    html = render_report_html(
        template_name="smd/dna_report.html",
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
    assert ">TMB</td>" in html
    assert ">HRD</td>" not in html
    assert "mut/Mb" in html
    assert "'value':" not in html
