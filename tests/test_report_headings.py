"""Offline report JSON regressions; no Flask application or database is started."""

import importlib.util
import sys
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load_module(name, relative_path, monkeypatch):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def report_modules(monkeypatch):
    # Replace only host composition imports; execute the real report builders and
    # summary methods. A missing database or app must never be opened by these tests.
    dependencies = {
        "coyote": {},
        "flask": {"current_app": SimpleNamespace(config={})},
        "flask_login": {"current_user": None},
        "coyote.extensions": {"store": None},
        "coyote.util.common_utility": {"CommonUtility": type("CommonUtility", (), {})},
    }
    for name, attributes in dependencies.items():
        module = ModuleType(name)
        module.__dict__.update(attributes)
        monkeypatch.setitem(sys.modules, name, module)
    load_module("coyote.__version__", "coyote/__version__.py", monkeypatch)
    documents = load_module(
        "report_documents_test", "coyote/util/report/report_documents.py", monkeypatch
    )
    summaries = load_module("summary_test", "coyote/blueprints/common/util.py", monkeypatch)
    return documents, summaries.BPCommonUtility


@pytest.mark.parametrize(
    "assay,group,sample_no,question",
    [
        ("hema-panel", "hematology", 1, "<DIAGNOSIS>"),
        ("myeloid-panel", "myeloid", 1, "<DIAGNOSIS>"),
        ("hema-panel", "hematology", 2, "Hematologisk neoplasi"),
        ("tumwgs-hema", "tumwgs", 1, "Hematologisk neoplasi"),
        ("tumwgs-solid", "tumwgs", 1, "Solid tumör"),
        ("solid-panel", "solid", 1, "Solid tumör"),
        ("swea-panel", "swea", 1, ""),
        ("gmsonco-panel", "gmsonco", 1, ""),
        ("other-panel", "other", 1, ""),
    ],
)
def test_dna_headings_use_existing_clinical_question(
    report_modules, assay, group, sample_no, question
):
    documents, _ = report_modules
    sample = {"name": "SYNTHETIC", "case_id": "CASE", "assay": assay, "sample_no": sample_no}
    document = documents.build_dna_document(
        sample=sample,
        assay_config={"reporting": {"report_header": "Analysrapport"}},
        report_sections=["SNV"],
        report_sections_data={"snvs": []},
        report_date=date(2026, 1, 1),
        report_timestamp="20260101",
        assay_group=group,
        genes_covered_in_panel={},
        author="Synthetic author",
        asp_url="",
    )
    suffix = " frågeställning" + (f" {question}" if question else "")
    sections = {section["key"]: section for section in document["sections"]}
    assert document["title"] == f"Analysrapport -{suffix} - SYNTHETIC"
    assert sections["results"]["heading"] == "Analysresultat" + suffix
    assert sections["conclusion"]["heading"] == "Slutsats" + suffix
    assert sections["snvs"]["heading"] == "Kliniskt relevanta mutationer (SNVs och små INDELs)"
    fields = {field["label"]: field["value"] for field in document["report"]["fields"]}
    assert fields.get("Frågeställning", "") == question
    assert document["report"]["sample_id"] == "CASE"
    assert document["report"]["report_id"] == "CASE_NONE.20260101"


@pytest.mark.parametrize("assay", ["hema-panel", "tumwgs-hema", "tumwgs-solid"])
def test_generated_summary_uses_mutation_heading(report_modules, assay):
    _, summaries = report_modules
    summary = summaries.generate_summary_text(
        sample_ids=["SYNTHETIC"],
        assay_config={"assay_name": assay},
        assay_panel_doc={},
        summary_sections_data={"snvs": []},
        genes_chosen=[],
        checked_genelists=[],
    )
    assert "**Kliniskt relevanta mutationer (SNVs och små INDELs):**" in summary
    assert "Vid analysen har inga somatiskt förvärvade mutationer" in summary


def test_rna_conclusion_keeps_existing_question(report_modules):
    documents, _ = report_modules
    document = documents.build_rna_document(
        sample={"name": "SYNTHETIC", "assay": "fusions"},
        assay="fusions",
        fusions=[],
        report_header="RNA report",
        analysis_method="RNA",
        analysis_desc=None,
        class_desc=[],
        class_desc_short=[],
        report_date=date(2026, 1, 1),
        author="Synthetic author",
    )
    sections = {section["key"]: section for section in document["sections"]}
    assert document["title"] == "RNA report - SYNTHETIC"
    assert sections["fusions"]["heading"] == "Analysresultat"
    assert sections["conclusion"]["heading"] == "Slutsats frågeställning RNA fusions"
