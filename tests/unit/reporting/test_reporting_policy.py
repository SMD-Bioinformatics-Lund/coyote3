"""Report eligibility, scoped annotation selection and governed metadata regressions."""

from copy import deepcopy

import mongomock
import pytest
from pydantic import ValidationError

from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.service import rendered_summary
from api.application.reporting.clinical_rules.validation import validate_rule_set
from api.application.reporting.dna_report_payload import filter_variants_for_report
from api.application.reporting.eligibility import reportable_tiers
from api.application.reporting.report_renderer import _template_defaults
from api.contracts.schemas.assay import ReportableTiersDoc
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
from scripts import migrate_reporting_policy
from scripts.migrate_reporting_policy import metadata_draft
from tests.unit.reporting.test_clinical_rules import _context, _document


@pytest.mark.parametrize("value", [[0], [5], [True], [1.5], ["1.0"], None, "1,2"])
def test_tier_policy_rejects_invalid_values(value):
    with pytest.raises(ValidationError):
        ReportableTiersDoc(SNV=value)


def test_tier_policy_preserves_empty_and_normalizes_form_selections():
    assert reportable_tiers({}, "SNV") == [1, 2, 3]
    assert reportable_tiers({"reportable_tiers": {"SNV": []}}, "SNV") == []
    assert ReportableTiersDoc(SNV=["3", "1", "3"]).SNV == [1, 3]


def test_report_filter_respects_tiers_genes_and_blacklist():
    variants = [
        {"classification": {"class": tier}, "INFO": {"selected_CSQ": {"SYMBOL": "TP53"}}}
        for tier in [1, 2, 3, 4, 999]
    ]
    variants.append({**deepcopy(variants[0]), "blacklist": True})
    assert [
        v["classification"]["class"] for v in filter_variants_for_report(variants, [], [1, 4])
    ] == [1, 4]
    assert filter_variants_for_report(variants, [], []) == []
    assert filter_variants_for_report(variants, ["BRAF"], [1, 2, 3]) == []
    assert filter_variants_for_report(variants, [], [1, 2, 3], restrict_to_genes=True) == []


@pytest.mark.parametrize(
    "group,analyte,subpanel,paired,question,suffix",
    [
        (
            "myeloid",
            "dna",
            "hem-snabb",
            True,
            "Hematologisk neoplasi",
            ": fullständig parad analys",
        ),
        ("myeloid", "dna", "hem-snabb", False, "<DIAGNOSIS>", ": preliminär oparad analys"),
        ("myeloid", "dna", "base", True, "Hematologisk neoplasi", ""),
        ("hematology", "dna", "base", False, "<DIAGNOSIS>", ""),
        ("solid", "dna", "bp", False, "Bröst-Pilot", ""),
        ("solid", "dna", "lung", False, "lung", ""),
        ("solid", "dna", "base", False, "", ""),
        ("demo", "rna", "base", False, "Fusionsgenanalys", ""),
        ("myeloid", "rna", "hem-snabb", True, "Fusionsgenanalys", ": fullständig parad analys"),
    ],
)
def test_metadata_migration_preserves_conditional_outputs(
    group, analyte, subpanel, paired, question, suffix
):
    source = _document(status="published", active=True).model_dump(mode="python", by_alias=True)
    original = deepcopy(source)
    source["scope"]["analyte"] = analyte
    candidate = metadata_draft(source, group=group, version=2, actor="migration-test")
    parsed = ClinicalRuleSetDoc.model_validate(candidate)
    assert parsed.status == "draft"
    assert not parsed.active
    assert parsed.review.clinical_reviewer is None
    assert parsed.minimum_engine_version == 2
    assert validate_rule_set(parsed).valid
    context = _context()
    context.sample.subpanel_id = subpanel
    context.sample.paired = paired
    evaluation = ClinicalRuleEvaluator().evaluate(context, parsed, reporting_analyses=set())
    assert evaluation.sections.get("clinical_question", [""])[0] == question
    assert evaluation.sections.get("report_header_suffix", [""])[0] == suffix
    assert "clinical_question" not in rendered_summary(evaluation)
    assert source["blocks"] == original["blocks"]
    assert metadata_draft(candidate, group=group, version=3, actor="migration-test") is None


def test_unconfigured_group_has_no_invented_report_metadata():
    source = _document(status="published", active=True).model_dump(mode="python", by_alias=True)
    assert metadata_draft(source, group="demo", version=2, actor="migration-test") is None


def test_metadata_sections_reject_ambiguous_outputs_and_invalid_modes():
    source = _document(status="published", active=True).model_dump(mode="python", by_alias=True)
    document = ClinicalRuleSetDoc.model_validate(
        metadata_draft(source, group="hematology", version=2, actor="migration-test")
    )
    block = document.blocks[-1]
    block.match_strategy = "all_matches"
    block.rules[0].condition = None
    with pytest.raises(ValueError, match="at most one output"):
        ClinicalRuleEvaluator().evaluate(_context(), document, reporting_analyses=set())
    block.show_heading = True
    assert not validate_rule_set(document).valid
    document.minimum_engine_version = 1
    assert any("minimum_engine_version" in error for error in validate_rule_set(document).errors)


def test_renderer_does_not_mutate_aspc_or_duplicate_metadata_in_summary():
    context = {
        "assay_config": {"reporting": {"report_header": "Report"}},
        "report_header": "Report",
        "clinical_rule_evaluation": {
            "sections": {"report_header_suffix": [": paired"], "clinical_question": ["Question"]}
        },
    }
    original = deepcopy(context)
    prepared = _template_defaults(context, analyte="dna", preview=True)
    assert prepared["assay_config"]["reporting"]["report_header"] == "Report: paired"
    assert prepared["report_header"] == "Report: paired"
    assert context == original


def test_migration_dry_run_apply_history_and_idempotency(monkeypatch):
    db = mongomock.MongoClient().test
    source = _document(status="published", active=True).model_dump(mode="python", by_alias=True)
    db.assay_specific_panels.insert_one({"asp_id": "assay_1", "asp_group": "myeloid", "version": 1})
    db.clinical_rule_sets.insert_one(source)
    db.asp_configs.insert_one(
        {
            "aspc_id": "assay_1_base_testing",
            "asp_id": "assay_1",
            "asp_group": "gmsonco",
            "version": 1,
            "is_active": True,
            "reporting": {},
        }
    )
    before = deepcopy(db.clinical_rule_sets.find_one())
    counts = migrate_reporting_policy.migrate(db, actor="operator")
    assert counts == {"aspc_revisions": 1, "rule_drafts": 1, "open_rule_drafts": 0}
    assert db.asp_configs.count_documents({}) == 1
    assert db.clinical_rule_sets.count_documents({}) == 1
    transactions = []

    def transaction(_client, callback):
        transactions.append(True)
        return callback(None)

    monkeypatch.setattr(migrate_reporting_policy, "run_transaction", transaction)
    assert migrate_reporting_policy.migrate(db, actor="operator", apply=True) == counts
    assert transactions == [True]
    assert db.clinical_rule_sets.find_one({"_id": source["_id"]}) == before
    assert db.clinical_rule_revisions.count_documents({}) == 1
    assert db.asp_configs.find_one({"is_active": True})["reporting"]["reportable_tiers"]["SNV"] == [
        1,
        2,
    ]
    assert "reportable_tiers" not in db.asp_configs.find_one({"version": 1})["reporting"]
    assert migrate_reporting_policy.migrate(db, actor="operator", apply=True) == {
        "aspc_revisions": 0,
        "rule_drafts": 0,
        "open_rule_drafts": 1,
    }
