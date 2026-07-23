"""Tests for clinical reporting rule compilation and evaluation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from bson import ObjectId

from api.application.reporting.clinical_rules.compiler import ClinicalRuleCompiler
from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.facts import PreparedReportContext
from api.application.reporting.clinical_rules.preparation import prepare_report_context
from api.application.reporting.clinical_rules.publisher import ClinicalRulePublisher
from api.application.reporting.clinical_rules.service import ClinicalRuleService
from api.contracts.schemas.clinical_rules import ClinicalRuleReleaseDoc

RULES_ROOT = Path(__file__).resolve().parents[3] / "clinical_reporting_rules"


def _release(source_path: Path) -> ClinicalRuleReleaseDoc:
    compiler = ClinicalRuleCompiler()
    source = compiler.load(source_path)
    return ClinicalRuleReleaseDoc(
        _id=ObjectId(),
        rule_set_id=source.rule_set.rule_set_id,
        version=source.rule_set.version,
        status="active",
        content_hash=compiler.content_hash(source),
        source_path=source_path.as_posix(),
        source=source,
        published_by="tester",
        published_on=datetime.now(timezone.utc),
    )


def _context(*, tier: int = 1) -> PreparedReportContext:
    return PreparedReportContext(
        sample={
            "name": "seed_sample",
            "assay": "seed_assay",
            "subpanel_id": "base",
            "profile": "production",
            "omics_layer": "dna",
        },
        asp={"asp_id": "seed_assay", "asp_group": "hematology", "accredited": True},
        aspc={
            "aspc_id": "seed_assay_base_production",
            "asp_id": "seed_assay",
            "asp_group": "hematology",
            "subpanel_id": "base",
            "environment": "production",
            "reporting": {},
        },
        findings=[
            {
                "kind": "snv",
                "gene": "TP53",
                "genes": ["TP53"],
                "tier": tier,
                "hgvsp": "p.Arg1Gly",
                "hgvsc": "c.1A>G",
                "case_vaf": 0.25,
                "case_vaf_percent": 25.0,
            }
        ],
        aggregates={
            "finding_count": 1,
            "snv_count": 1,
            "cnv_count": 0,
            "fusion_count": 0,
            "translocation_count": 0,
            "biomarker_count": 0,
            "tier_1_count": int(tier == 1),
            "tier_2_count": int(tier == 2),
            "tier_3_count": int(tier == 3),
            "has_reportable_findings": True,
        },
    )


def _rna_context() -> PreparedReportContext:
    return PreparedReportContext(
        sample={
            "name": "seed_rna_sample",
            "assay": "seed_rna_assay",
            "subpanel_id": "base",
            "profile": "production",
            "omics_layer": "rna",
        },
        asp={"asp_id": "seed_rna_assay", "asp_group": "rna"},
        aspc={
            "aspc_id": "seed_rna_assay_base_production",
            "asp_id": "seed_rna_assay",
            "asp_group": "rna",
            "subpanel_id": "base",
            "environment": "production",
            "reporting": {},
        },
        findings=[
            {
                "kind": "fusion",
                "gene": None,
                "genes": ["KMT2A", "AFF1"],
                "tier": 1,
                "fusion_gene_1": "KMT2A",
                "fusion_gene_2": "AFF1",
            }
        ],
        aggregates={
            "finding_count": 1,
            "snv_count": 0,
            "cnv_count": 0,
            "fusion_count": 1,
            "translocation_count": 0,
            "biomarker_count": 0,
            "tier_1_count": 1,
            "tier_2_count": 0,
            "tier_3_count": 0,
            "has_reportable_findings": True,
        },
    )


def test_generic_rules_compile_deterministically():
    compiler = ClinicalRuleCompiler()
    source = compiler.load(RULES_ROOT / "generic_dna.yaml")

    first = compiler.content_hash(source)
    second = compiler.content_hash(compiler.load(RULES_ROOT / "generic_dna.yaml"))

    assert first == second
    assert len(first) == 64


def test_all_repository_rule_sources_compile():
    compiler = ClinicalRuleCompiler()

    sources = [compiler.load(path) for path in sorted(RULES_ROOT.glob("*.yaml"))]

    assert {source.rule_set.rule_set_id for source in sources} == {
        "endometrial_dna_reporting",
        "generic_dna_reporting",
        "generic_rna_reporting",
    }


def test_draft_rules_validate_but_cannot_publish():
    source_path = RULES_ROOT / "endometrial_dna.draft.yaml"
    compiler = ClinicalRuleCompiler()
    compiler.load(source_path)

    with pytest.raises(ValueError, match="only active sources"):
        ClinicalRulePublisher(repository=object(), compiler=compiler).publish(
            source_path,
            published_by="tester",
        )


def test_unknown_fact_is_rejected(tmp_path):
    source = (RULES_ROOT / "generic_dna.yaml").read_text(encoding="utf-8")
    source = source.replace("finding.kind", "finding.unregistered_fact", 1)
    path = tmp_path / "invalid.yaml"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported clinical rule fact"):
        ClinicalRuleCompiler().load(path)


def test_collection_operator_requires_list_value(tmp_path):
    source = (RULES_ROOT / "generic_dna.yaml").read_text(encoding="utf-8")
    source = source.replace(
        "operator: eq\n        value: snv", "operator: in\n        value: snv", 1
    )
    path = tmp_path / "invalid-operator-value.yaml"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match="requires a list value"):
        ClinicalRuleCompiler().load(path)


def test_template_cannot_use_unapproved_jinja_global(tmp_path):
    source = (RULES_ROOT / "generic_dna.yaml").read_text(encoding="utf-8")
    source = source.replace(
        "{{ finding.gene }} {{ finding.hgvsp or finding.hgvsc }}",
        "{{ range(10) }}",
        1,
    )
    path = tmp_path / "invalid-template-global.yaml"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported template variables"):
        ClinicalRuleCompiler().load(path)


def test_preparation_exposes_case_and_control_vaf_percentages():
    context = prepare_report_context(
        sample={
            "name": "seed_sample",
            "assay": "seed_assay",
            "subpanel_id": "base",
            "profile": "production",
        },
        asp={"asp_id": "seed_assay"},
        aspc={
            "aspc_id": "seed_assay_base_production",
            "asp_id": "seed_assay",
            "subpanel_id": "base",
            "environment": "production",
        },
        analyte="dna",
        applied_gene_lists=[],
        report_sections_data={
            "snvs": [
                {
                    "INFO": {
                        "selected_CSQ": {
                            "SYMBOL": "TP53",
                            "HGVSc": "c.1A>G",
                            "HGVSp": "p.Arg1Gly",
                        }
                    },
                    "GT": [
                        {"type": "case", "AF": 0.25124},
                        {"type": "control", "AF": 0.007},
                    ],
                    "classification": {"class": 1},
                }
            ]
        },
    )

    finding = context.findings[0]
    assert finding.case_vaf == 0.25124
    assert finding.case_vaf_percent == 25.124
    assert finding.control_vaf == 0.007
    assert finding.control_vaf_percent == 0.7


def test_evaluator_applies_first_matching_finding_rule_and_records_trace():
    release = _release(RULES_ROOT / "generic_dna.yaml")
    result = ClinicalRuleEvaluator().evaluate(_context(tier=1), release)

    rendered = result.sections["Kliniskt relevanta fynd"]
    assert len(rendered) == 1
    assert "TP53" in rendered[0]
    assert "25.0 %" in rendered[0]
    assert "Tier I" in rendered[0]
    assert any(entry.rule_id == "dna_tier_1_finding" and entry.matched for entry in result.trace)
    assert not any(
        entry.rule_id == "dna_tier_2_finding" and entry.matched for entry in result.trace
    )


def test_rna_rules_render_prepared_fusion():
    release = _release(RULES_ROOT / "generic_rna.yaml")

    result = ClinicalRuleEvaluator().evaluate(_rna_context(), release)

    assert result.sections["Kliniskt relevanta fynd"] == [
        "En fusion mellan KMT2A och AFF1 påvisades och är klassificerad som Tier 1."
    ]


def test_service_returns_none_without_aspc_release_reference():
    context = _context()
    service = ClinicalRuleService(repository=object())

    assert (
        service.evaluate_bound_release(
            aspc=context.aspc.model_dump(mode="python"),
            context=context,
        )
        is None
    )


def test_service_rejects_release_scope_mismatch():
    release = _release(RULES_ROOT / "generic_dna.yaml")

    class _Repository:
        @staticmethod
        def get_referenced_release(_reference):
            return release

    context = _context().model_copy(
        update={
            "sample": _context().sample.model_copy(update={"omics_layer": "rna"}),
        }
    )
    bound_aspc = context.aspc.model_dump(mode="python")
    bound_aspc["reporting"]["clinical_rule_release"] = {
        "release_id": release.id_,
        "rule_set_id": release.rule_set_id,
        "version": release.version,
        "content_hash": release.content_hash,
    }

    with pytest.raises(ValueError, match="scope does not match"):
        ClinicalRuleService(_Repository()).evaluate_bound_release(
            aspc=bound_aspc,
            context=context,
        )
