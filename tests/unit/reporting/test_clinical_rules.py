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
            "assay": "fusion",
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


def test_hema_base_rules_compile_deterministically():
    compiler = ClinicalRuleCompiler()
    source_path = RULES_ROOT / "hema_GMSv1" / "base.draft.yaml"
    source = compiler.load(source_path)

    first = compiler.content_hash(source)
    second = compiler.content_hash(compiler.load(source_path))

    assert first == second
    assert len(first) == 64


def test_all_repository_rule_sources_compile():
    compiler = ClinicalRuleCompiler()

    sources = [compiler.load(path) for path in compiler.discover(RULES_ROOT)]

    assert {source.rule_set.rule_set_id for source in sources} == {
        "RNA_fusion__base",
        "fusion__base",
        "hema_GMSv1__base",
        "myeloid_GMSv1__base",
        "solidRNA_GMSv5__base",
        "solid_GMSv3__base",
        "solid_GMSv3__endometrie",
        "tumwgs_hema__base",
        "tumwgs_solid__base",
    }


def test_repository_path_must_match_assay_and_subpanel_scope(tmp_path):
    rules_root = tmp_path / "clinical_reporting_rules"
    wrong_assay_dir = rules_root / "another_assay"
    wrong_assay_dir.mkdir(parents=True)
    source = (RULES_ROOT / "hema_GMSv1" / "base.draft.yaml").read_text(encoding="utf-8")
    path = wrong_assay_dir / "base.draft.yaml"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match="does not match its assay/subpanel scope"):
        ClinicalRuleCompiler().load(path)


def test_draft_rules_validate_but_cannot_publish():
    source_path = RULES_ROOT / "solid_GMSv3" / "endometrie.draft.yaml"
    compiler = ClinicalRuleCompiler()
    compiler.load(source_path)

    with pytest.raises(ValueError, match="only active sources"):
        ClinicalRulePublisher(repository=object(), compiler=compiler).publish(
            source_path,
            published_by="tester",
        )


def test_unknown_fact_is_rejected(tmp_path):
    source = (RULES_ROOT / "solid_GMSv3" / "endometrie.draft.yaml").read_text(encoding="utf-8")
    source = source.replace("finding.kind", "finding.unregistered_fact", 1)
    path = tmp_path / "invalid.yaml"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported clinical rule fact"):
        ClinicalRuleCompiler().load(path)


def test_collection_operator_requires_list_value(tmp_path):
    source = (RULES_ROOT / "solid_GMSv3" / "endometrie.draft.yaml").read_text(encoding="utf-8")
    source = source.replace(
        "operator: eq\n        value: snv", "operator: in\n        value: snv", 1
    )
    path = tmp_path / "invalid-operator-value.yaml"
    path.write_text(source, encoding="utf-8")

    with pytest.raises(ValueError, match="requires a list value"):
        ClinicalRuleCompiler().load(path)


def test_template_cannot_use_unapproved_jinja_global(tmp_path):
    source = (RULES_ROOT / "solid_GMSv3" / "endometrie.draft.yaml").read_text(encoding="utf-8")
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


def test_hema_GMSv1_tier_composition_is_verbatim():
    def variant(gene: str, tier: int, vaf: float) -> dict:
        return {
            "INFO": {"selected_CSQ": {"SYMBOL": gene}},
            "GT": [{"type": "case", "AF": vaf}],
            "classification": {"class": tier},
        }

    context = prepare_report_context(
        sample={
            "name": "seed_sample",
            "assay": "seed_assay",
            "subpanel_id": "base",
            "profile": "production",
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
    release = _release(RULES_ROOT / "hema_GMSv1" / "base.draft.yaml")

    result = ClinicalRuleEvaluator().evaluate(context, release)

    assert result.sections["Kliniskt relevanta SNVs och små INDELs"] == [
        "Vid analysen finner man en mutation av stark klinisk signifikans (Tier I) "
        "i TP53 (i 90% av läsningarna). Vidare ses tre mutationer av potentiell "
        "klinisk signifikans (Tier II): en i PTEN (87%) och två i PIK3CA "
        "(67% respektive 66%). "
    ]


def test_hema_GMSv1_negative_result_and_conclusion_are_verbatim():
    release = _release(RULES_ROOT / "hema_GMSv1" / "base.draft.yaml")
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
    result = ClinicalRuleEvaluator().evaluate(context, release)

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
    accredited_result = ClinicalRuleEvaluator().evaluate(
        PreparedReportContext.model_validate(accredited_payload),
        release,
    )
    assert accredited_result.sections["Report conclusion"] == [
        "För ytterligare information om utförd analys och beskrivning av somatiskt "
        "förvärvade mutationer, var god se bifogad rapport. "
    ]


def test_solid_GMSv3_tier_two_multi_gene_edge_case_is_verbatim():
    def variant(gene: str, vaf: float) -> dict:
        return {
            "INFO": {"selected_CSQ": {"SYMBOL": gene}},
            "GT": [{"type": "case", "AF": vaf}],
            "classification": {"class": 2},
        }

    context = prepare_report_context(
        sample={
            "name": "seed_sample",
            "assay": "seed_assay",
            "subpanel_id": "base",
            "profile": "production",
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
    release = _release(RULES_ROOT / "solid_GMSv3" / "base.draft.yaml")

    result = ClinicalRuleEvaluator().evaluate(context, release)

    assert result.sections["Kliniskt relevanta SNVs och små INDELs"] == [
        "Vid analysen finner man två varianter av potentiell klinisk signifikans "
        "(Tier II): en i TP53 (90% av läsningarna) och en i PTEN (80%). "
    ]


def test_fusion_report_text_is_verbatim():
    release = _release(RULES_ROOT / "fusion" / "base.draft.yaml")
    result = ClinicalRuleEvaluator().evaluate(_rna_context(), release)

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
            "RNA_fusion",
            "RNA har extraherats från insänt prov och analyserats med massivt "
            "parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar "
            "160 kända fusionsgener vid solid tumörsjukdom som inkluderas i RNA "
            "fusionspanel (Twist Alliance CeGaT RNA Fusion Panel).\n\nFör ytterligare "
            "information om utförd analys och beskrivning av eventuellt funna "
            "fusionsgener, var god se bifogad rapport. Analysen omfattas inte av "
            "ackrediteringen.",
        ),
        (
            "solidRNA_GMSv5",
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
    release = _release(RULES_ROOT / assay_id / "base.draft.yaml")
    context_payload = _rna_context().model_dump(mode="python")
    context_payload["sample"]["assay"] = assay_id
    result = ClinicalRuleEvaluator().evaluate(
        PreparedReportContext.model_validate(context_payload),
        release,
    )

    assert result.sections["Report summary"] == [expected]


@pytest.mark.parametrize("assay_id", ["tumwgs_hema", "tumwgs_solid"])
def test_tumwgs_report_text_is_verbatim(assay_id):
    release = _release(RULES_ROOT / assay_id / "base.draft.yaml")
    context_payload = _context().model_dump(mode="python")
    context_payload["sample"]["assay"] = assay_id
    result = ClinicalRuleEvaluator().evaluate(
        PreparedReportContext.model_validate(context_payload),
        release,
    )

    assert result.sections["Report summary"] == [
        "DNA har extraherats från insänt prov och analyserats med massivt parallell "
        "sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar hela genomet "
        "(WGS; whole genome sequencing) med indikationsspecifik analys av somatiska "
        "varianter (SNVs, indels, amplifieringar, homozygota deletioner samt större "
        "alleliska obalanser (förlust och överskott av genetiskt material). "
        "Korresponderande normalprov har använts som kontrollmaterial.\n\nFör "
        "ytterligare information om utförd analys och beskrivning av somatiskt "
        "förvärvade varianter, var god se bifogad rapport. Analysen omfattas inte av "
        "ackrediteringen."
    ]


def test_endometrial_workbook_wording_is_verbatim():
    release = _release(RULES_ROOT / "solid_GMSv3" / "endometrie.draft.yaml")
    result = ClinicalRuleEvaluator().evaluate(_context(tier=1), release)

    assert result.sections["Molecular classification"] == [
        "Varianter i TP53 är klassificerande samt riskstratifierande vid "
        "endometriecancer (WHO 5th ed./NVP 2026)."
    ]
    assert result.sections["Report conclusion"] == [
        "För ytterligare information om utförd analys och beskrivning av somatiskt "
        "förvärvade varianter, var god se bifogad rapport. Analysen omfattas inte av "
        "ackrediteringen."
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
    release = _release(RULES_ROOT / "hema_GMSv1" / "base.draft.yaml")

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
