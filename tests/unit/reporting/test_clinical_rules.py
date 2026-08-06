"""Tests for clinical reporting rule compilation and evaluation."""

from __future__ import annotations

from pathlib import Path

import pytest

from api.application.reporting.clinical_rules.compiler import ClinicalRuleCompiler
from api.application.reporting.clinical_rules.evaluator import (
    ClinicalRuleEvaluator,
    _condition_matches,
)
from api.application.reporting.clinical_rules.facts import PreparedReportContext
from api.application.reporting.clinical_rules.preparation import prepare_report_context
from api.application.reporting.clinical_rules.service import ClinicalRuleService
from api.contracts.schemas.clinical_rules import ClinicalRuleCondition, ClinicalRuleOperator

RULES_ROOT = Path(__file__).resolve().parents[3] / "clinical_reporting_rules"


def _evaluate(
    context: PreparedReportContext,
    source_path: Path,
    *,
    reporting_analyses: set[str] | None = None,
):
    compiler = ClinicalRuleCompiler()
    source = compiler.load(source_path)
    return ClinicalRuleEvaluator().evaluate(
        context,
        source,
        source_path=source_path,
        content_hash=compiler.content_hash(source),
        reporting_analyses=reporting_analyses or set(source.analyses),
    )


def _context(*, tier: int = 1) -> PreparedReportContext:
    return PreparedReportContext(
        sample={
            "name": "seed_sample",
            "asp_id": "seed_assay",
            "subpanel_id": "base",
            "environment": "production",
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
            "asp_id": "fusion",
            "subpanel_id": "base",
            "environment": "production",
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
                "fusion_breakpoint_1": "11:118354227",
                "fusion_breakpoint_2": "4:87957570",
                "fusion_spanning_pairs": 12,
                "fusion_spanning_reads": 9,
                "fusion_annotation": "Granskad klinisk kommentar.",
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


def test_hema_base_rules_compile_deterministically():
    compiler = ClinicalRuleCompiler()
    source_path = RULES_ROOT / "hema_gmsv1" / "base.yaml"
    source = compiler.load(source_path)

    first = compiler.content_hash(source)
    second = compiler.content_hash(compiler.load(source_path))

    assert first == second
    assert len(first) == 64


def test_all_repository_rule_sources_compile():
    compiler = ClinicalRuleCompiler()

    sources = [compiler.load(path) for path in compiler.discover(RULES_ROOT)]

    assert {source.rule_set.rule_set_id for source in sources} == {
        "rna_fusion__base",
        "fusion__base",
        "hema_gmsv1__base",
        "myeloid_gmsv1__base",
        "solidrna_gmsv5__base",
        "solid_gmsv3__base",
        "solid_gmsv3__endometrie",
        "tumwgs_hema__base",
        "tumwgs_solid__base",
    }


def test_repository_path_must_match_assay_and_subpanel_scope(tmp_path):
    rules_root = tmp_path / "clinical_reporting_rules"
    wrong_assay_dir = rules_root / "another_assay"
    wrong_assay_dir.mkdir(parents=True)
    source = (RULES_ROOT / "hema_gmsv1" / "base.yaml").read_text(encoding="utf-8")
    path = wrong_assay_dir / "base.yaml"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match="does not match its assay/subpanel scope"):
        ClinicalRuleCompiler().load(path)


def test_rule_source_has_a_stable_static_scope():
    source_path = RULES_ROOT / "solid_gmsv3" / "endometrie.yaml"
    compiler = ClinicalRuleCompiler()
    source = compiler.load(source_path)

    assert source.rule_set.rule_set_id == "solid_gmsv3__endometrie"
    assert source.analyses["BIOMARKER"].enabled is False


def test_unknown_fact_is_rejected(tmp_path):
    source = (RULES_ROOT / "solid_gmsv3" / "endometrie.yaml").read_text(encoding="utf-8")
    source = source.replace("finding.kind", "finding.unregistered_fact", 1)
    path = tmp_path / "invalid.yaml"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported clinical rule fact"):
        ClinicalRuleCompiler().load(path)


def test_collection_operator_requires_list_value(tmp_path):
    source = (RULES_ROOT / "solid_gmsv3" / "endometrie.yaml").read_text(encoding="utf-8")
    source = source.replace(
        "operator: in\n            value: [MLH1, MSH2, MSH6, PMS2]",
        "operator: in\n            value: MLH1",
        1,
    )
    path = tmp_path / "invalid-operator-value.yaml"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match="requires a list value"):
        ClinicalRuleCompiler().load(path)


def test_template_cannot_use_unapproved_jinja_global(tmp_path):
    source = (RULES_ROOT / "solid_gmsv3" / "endometrie.yaml").read_text(encoding="utf-8")
    source = source.replace(
        "{{ finding.gene }}",
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
            "asp_id": "seed_assay",
            "subpanel_id": "base",
            "environment": "production",
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


def test_hema_introduction_uses_the_applied_snv_gene_list():
    context = prepare_report_context(
        sample={
            "name": "seed_sample",
            "asp_id": "hema_gmsv1",
            "subpanel_id": "base",
            "environment": "production",
            "paired": True,
        },
        asp={
            "asp_id": "hema_gmsv1",
            "germline_genes": ["CEBPA"],
        },
        aspc={
            "aspc_id": "hema_gmsv1_base_production",
            "asp_id": "hema_gmsv1",
            "subpanel_id": "base",
            "environment": "production",
            "reporting": {
                "general_report_summary": (
                    "DNA har extraherats från insänt prov och analyserats med massivt "
                    "parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen "
                    "omfattar exoner i 385 gener som inkluderas i GMS-HEM v1.1 "
                    "sekvenseringspanel. "
                )
            },
        },
        analyte="dna",
        applied_gene_lists=[
            {
                "isgl_id": "hematology_myeloid",
                "selected_for": ["snv"],
                "genes": [f"GENE{index}" for index in range(196)] + ["CEBPA"],
                "germline_genes": ["CEBPA"],
            }
        ],
        report_sections_data={},
    )
    result = _evaluate(context, RULES_ROOT / "hema_gmsv1" / "base.yaml", reporting_analyses={"SNV"})

    assert result.sections["Report introduction"] == [
        "DNA har extraherats från insänt prov och analyserats med massivt parallell "
        "sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar exoner i 385 "
        "gener som inkluderas i GMS-HEM v1.1 sekvenseringspanel. Analysen avser "
        "somatiska mutationer (hudbiopsi har använts som kontrollmaterial). Analysen "
        "omfattar genlistan: HEMATOLOGY_MYELOID som innefattar 197 gener. För CEBPA "
        "undersöks även konstitutionella mutationer."
    ]


def test_hema_gmsv1_tier_composition_is_verbatim():
    def variant(gene: str, tier: int, vaf: float) -> dict:
        return {
            "INFO": {"selected_CSQ": {"SYMBOL": gene}},
            "GT": [{"type": "case", "AF": vaf}],
            "classification": {"class": tier},
        }

    context = prepare_report_context(
        sample={
            "name": "seed_sample",
            "asp_id": "seed_assay",
            "subpanel_id": "base",
            "environment": "production",
        },
        asp={"asp_id": "seed_assay", "accredited": False},
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
                variant("TP53", 1, 0.90),
                variant("PTEN", 2, 0.87),
                variant("PIK3CA", 2, 0.67),
                variant("PIK3CA", 2, 0.66),
            ]
        },
    )
    result = _evaluate(context, RULES_ROOT / "hema_gmsv1" / "base.yaml", reporting_analyses={"SNV"})

    assert result.sections["Kliniskt relevanta SNVs och små INDELs"] == [
        "Vid analysen finner man en mutation av stark klinisk signifikans (Tier I) "
        "i TP53 (i 90% av läsningarna). Vidare ses tre mutationer av potentiell "
        "klinisk signifikans (Tier II): en i PTEN (87%) och två i PIK3CA "
        "(67% respektive 66%). "
    ]


def test_hema_gmsv1_negative_result_and_conclusion_are_verbatim():
    context_payload = _context(tier=1).model_dump(mode="python")
    context_payload["findings"] = []
    context_payload["asp"]["accredited"] = False
    context_payload["aggregates"] = {
        "finding_count": 0,
        "snv_count": 0,
        "cnv_count": 0,
        "fusion_count": 0,
        "translocation_count": 0,
        "biomarker_count": 0,
        "tier_1_count": 0,
        "tier_2_count": 0,
        "tier_3_count": 0,
        "tier_summaries": [],
        "has_tiered_snvs": False,
        "has_reportable_findings": False,
    }
    context = PreparedReportContext.model_validate(context_payload)
    result = _evaluate(context, RULES_ROOT / "hema_gmsv1" / "base.yaml", reporting_analyses={"SNV"})

    assert result.sections["Kliniskt relevanta SNVs och små INDELs"] == [
        "Vid analysen har inga somatiskt förvärvade mutationer i undersökta gener påvisats."
    ]
    assert result.sections["Report conclusion"] == [
        "För ytterligare information om utförd analys och beskrivning av somatiskt "
        "förvärvade mutationer, var god se bifogad rapport. Analysen omfattas inte "
        "av ackrediteringen."
    ]
    assert result.section_headings == {
        "Kliniskt relevanta SNVs och små INDELs": True,
        "Report conclusion": False,
    }

    accredited_payload = context.model_dump(mode="python")
    accredited_payload["asp"]["accredited"] = True
    accredited_result = _evaluate(
        PreparedReportContext.model_validate(accredited_payload),
        RULES_ROOT / "hema_gmsv1" / "base.yaml",
        reporting_analyses={"SNV"},
    )
    assert accredited_result.sections["Report conclusion"] == [
        "För ytterligare information om utförd analys och beskrivning av somatiskt "
        "förvärvade mutationer, var god se bifogad rapport. "
    ]


def test_solid_gmsv3_tier_two_multi_gene_edge_case_is_verbatim():
    def variant(gene: str, vaf: float) -> dict:
        return {
            "INFO": {"selected_CSQ": {"SYMBOL": gene}},
            "GT": [{"type": "case", "AF": vaf}],
            "classification": {"class": 2},
        }

    context = prepare_report_context(
        sample={
            "name": "seed_sample",
            "asp_id": "seed_assay",
            "subpanel_id": "base",
            "environment": "production",
        },
        asp={"asp_id": "seed_assay", "accredited": False},
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
                variant("TP53", 0.90),
                variant("PTEN", 0.80),
            ]
        },
    )
    result = _evaluate(
        context, RULES_ROOT / "solid_gmsv3" / "base.yaml", reporting_analyses={"SNV"}
    )

    assert result.sections["Kliniskt relevanta SNVs och små INDELs"] == [
        "Vid analysen finner man två mutationer av potentiell klinisk signifikans "
        "(Tier II): en i TP53 (90% av läsningarna) och en i PTEN (80%). "
    ]


def test_fusion_report_text_includes_the_reviewed_finding():
    result = _evaluate(
        _rna_context(), RULES_ROOT / "fusion" / "base.yaml", reporting_analyses={"FUSION"}
    )

    assert result.sections["Report summary"] == [
        "RNA har extraherats från insänt prov och analyserats med massivt parallell "
        "sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar hela mRNA "
        "transkriptomet och avser detektion av fusionsgener.\n\nVid analysen finner "
        "man en fusion av stark klinisk signifikans (Tier I) mellan generna KMT2A "
        "och AFF1. De genomiska positionerna för brottspunkterna är 11:118354227 "
        "och 4:87957570.\n\nRearrangemanget är påvisat efter manuell eftergranskning "
        "av data där 12 läspar, och 9 läsningar direkt över brottspunkten ger stöd "
        "för en KMT2A::AFF1-genfusion.\n\nGranskad klinisk kommentar.\n\nFör ytterligare "
        "information om utförd analys och beskrivning av eventuellt funna fusionsgener, "
        "var god se bifogad rapport. RNA-seq-analys har gjorts som led i ett "
        "utvecklingsarbete och har ej debiterats. Analysen omfattas inte av "
        "ackrediteringen."
    ]


def test_fusion_report_text_keeps_the_approved_baseline_when_no_fusion_is_reportable():
    context_payload = _rna_context().model_dump(mode="python")
    context_payload["findings"] = []
    context_payload["aggregates"]["finding_count"] = 0
    context_payload["aggregates"]["fusion_count"] = 0
    context_payload["aggregates"]["has_reportable_findings"] = False
    result = _evaluate(
        PreparedReportContext.model_validate(context_payload),
        RULES_ROOT / "fusion" / "base.yaml",
        reporting_analyses={"FUSION"},
    )

    assert result.sections["Report summary"] == [
        "RNA har extraherats från insänt prov och analyserats med massivt parallell "
        "sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar hela mRNA "
        "transkriptomet och avser detektion av fusionsgener.\n\nFör ytterligare "
        "information om utförd analys och beskrivning av eventuellt funna fusionsgener, "
        "var god se bifogad rapport. RNA-seq-analys har gjorts som led i ett "
        "utvecklingsarbete och har ej debiterats. Analysen omfattas inte av "
        "ackrediteringen."
    ]


@pytest.mark.parametrize(
    ("assay_id", "expected"),
    [
        (
            "rna_fusion",
            "RNA har extraherats från insänt prov och analyserats med massivt "
            "parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar "
            "160 kända fusionsgener vid solid tumörsjukdom som inkluderas i RNA "
            "fusionspanel (Twist Alliance CeGaT RNA Fusion Panel).\n\nFör ytterligare "
            "information om utförd analys och beskrivning av eventuellt funna "
            "fusionsgener, var god se bifogad rapport. Analysen omfattas inte av "
            "ackrediteringen.",
        ),
        (
            "solidrna_gmsv5",
            "RNA har extraherats från insänt prov och analyserats med massivt "
            "parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar "
            "kända fusionsgener vid solid tumörsjukdom, se Analysbeskrivning nedan."
            "\n\nFör ytterligare information om utförd analys och beskrivning av "
            "eventuellt funna fusionsgener, var god se bifogad rapport. Analysen "
            "omfattas inte av ackrediteringen.",
        ),
    ],
)
def test_targeted_rna_report_text_is_verbatim(assay_id, expected):
    context_payload = _rna_context().model_dump(mode="python")
    context_payload["sample"]["asp_id"] = assay_id
    result = _evaluate(
        PreparedReportContext.model_validate(context_payload),
        RULES_ROOT / assay_id / "base.yaml",
        reporting_analyses={"FUSION"},
    )

    introduction, closing = expected.split("\n\n", 1)
    finding_text = (
        "Vid analysen finner man en fusion av stark klinisk signifikans (Tier I) "
        "mellan generna KMT2A och AFF1. De genomiska positionerna för brottspunkterna "
        "är 11:118354227 och 4:87957570.\n\nRearrangemanget är påvisat efter manuell "
        "eftergranskning av data där 12 läspar, och 9 läsningar direkt över "
        "brottspunkten ger stöd för en KMT2A::AFF1-genfusion.\n\n"
        "Granskad klinisk kommentar."
    )
    assert result.sections["Report summary"] == [f"{introduction}\n\n{finding_text}\n\n{closing}"]


@pytest.mark.parametrize("assay_id", ["tumwgs_hema", "tumwgs_solid"])
def test_tumwgs_report_text_is_verbatim(assay_id):
    context_payload = _context().model_dump(mode="python")
    context_payload["sample"]["asp_id"] = assay_id
    result = _evaluate(
        PreparedReportContext.model_validate(context_payload),
        RULES_ROOT / assay_id / "base.yaml",
        reporting_analyses={"SNV"},
    )

    assert result.sections["Report summary"] == [
        "DNA har extraherats från insänt prov och analyserats med massivt parallell "
        "sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar hela genomet "
        "(WGS; whole genome sequencing) med indikationsspecifik analys av somatiska "
        "mutationer (SNVs, indels, amplifieringar, homozygota deletioner samt större "
        "alleliska obalanser (förlust och överskott av genetiskt material). "
        "Korresponderande normalprov har använts som kontrollmaterial.\n\nFör "
        "ytterligare information om utförd analys och beskrivning av somatiskt "
        "förvärvade mutationer, var god se bifogad rapport. Analysen omfattas inte av "
        "ackrediteringen."
    ]


def test_endometrial_workbook_wording_is_verbatim():
    result = _evaluate(
        _context(tier=1), RULES_ROOT / "solid_gmsv3" / "endometrie.yaml", reporting_analyses={"SNV"}
    )

    assert result.sections["Molecular classification"] == [
        "Varianter i TP53 är klassificerande samt riskstratifierande vid "
        "endometriecancer (WHO 5th ed./NVP 2026)."
    ]
    assert result.sections["Report conclusion"] == [
        "För ytterligare information om utförd analys och beskrivning av somatiskt "
        "förvärvade mutationer, var god se bifogad rapport. Analysen omfattas inte av "
        "ackrediteringen."
    ]


def test_service_uses_base_yaml_when_the_selected_subpanel_has_no_file():
    context_payload = _context().model_dump(mode="python")
    context_payload["sample"]["asp_id"] = "hema_gmsv1"
    context_payload["asp"]["asp_id"] = "hema_gmsv1"
    context_payload["aspc"]["asp_id"] = "hema_gmsv1"
    context_payload["aspc"]["subpanel_id"] = "hem-snabb"
    context_payload["aspc"]["reporting"] = {"report_sections": ["SNV"]}
    context = PreparedReportContext.model_validate(context_payload)

    result = ClinicalRuleService().evaluate(
        aspc=context.aspc.model_dump(mode="python"), context=context
    )

    assert result.source.rule_set_id == "hema_gmsv1__base"


def test_disabled_yaml_analysis_does_not_emit_text_even_when_the_aspc_allows_it():
    source_path = RULES_ROOT / "hema_gmsv1" / "base.yaml"
    result = _evaluate(_context(), source_path, reporting_analyses={"SNV", "CNV"})

    assert "CNV" not in "\n".join(result.sections)


@pytest.mark.parametrize(
    ("condition", "scope", "expected", "exists"),
    [
        (
            ClinicalRuleCondition(
                fact="finding.genes", operator=ClinicalRuleOperator.CONTAINS, value="TP53"
            ),
            {"finding": {"genes": ["TP53", "KRAS"]}},
            True,
            True,
        ),
        (
            ClinicalRuleCondition(
                fact="finding.genes", operator=ClinicalRuleOperator.OVERLAPS, value=["KRAS", "BRAF"]
            ),
            {"finding": {"genes": ["TP53", "KRAS"]}},
            True,
            True,
        ),
        (
            ClinicalRuleCondition(
                fact="finding.case_vaf", operator=ClinicalRuleOperator.GTE, value=0.1
            ),
            {"finding": {"case_vaf": "not-numeric"}},
            False,
            True,
        ),
        (
            ClinicalRuleCondition(
                fact="finding.hgvsp", operator=ClinicalRuleOperator.EXISTS, value=False
            ),
            {"finding": {}},
            True,
            False,
        ),
    ],
)
def test_rule_conditions_fail_closed_for_missing_or_incompatible_facts(
    condition, scope, expected, exists
):
    """Rule predicates do not render text when facts are absent or incomparable."""
    assert _condition_matches(condition, scope) == (expected, exists)
