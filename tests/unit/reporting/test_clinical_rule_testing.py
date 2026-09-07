"""Read-only sample-backed clinical rule preview tests."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.service import ClinicalRuleService
from api.application.reporting.clinical_rules.testing import ClinicalRuleTestingService
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc
from api.domain.core.exceptions import AppError
from tests.unit.reporting.test_clinical_rules import _context, _document


class RuleRepository:
    def __init__(self, document=None):
        self.document = document

    def get(self, _document_id):
        return deepcopy(self.document)


class SampleRepository:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.call = None

    def search_samples_for_admin(self, **kwargs):
        self.call = kwargs
        return deepcopy(self.rows), len(self.rows)


class Workflow:
    def __init__(self, evaluation):
        self.evaluation = evaluation
        self.call = None

    def build_report_payload(self, **kwargs):
        self.call = kwargs
        if isinstance(self.evaluation, Exception):
            raise self.evaluation
        return "template.html", {"clinical_rule_evaluation": self.evaluation}, []


def service(*, document=None, rows=None, evaluation=None):
    return ClinicalRuleTestingService(
        rule_repository=RuleRepository(document if document is not None else _document()),
        sample_repository=SampleRepository(rows),
        assay_panel_repository=object(),
        assay_configuration_repository=object(),
        dna_workflow=Workflow(evaluation),
        rna_workflow=Workflow(evaluation),
    )


def test_from_store_builds_read_only_workflows(monkeypatch) -> None:
    dna = object()
    rna = object()
    monkeypatch.setattr(
        "api.application.reporting.clinical_rules.testing.DNAWorkflowService.from_store",
        lambda store: dna,
    )
    monkeypatch.setattr(
        "api.application.reporting.clinical_rules.testing.RNAWorkflowService.from_store",
        lambda store: rna,
    )
    store = SimpleNamespace(
        clinical_rule_set_repository=object(),
        sample_repository=object(),
        assay_panel_repository=object(),
        assay_configuration_repository=object(),
    )

    result = ClinicalRuleTestingService.from_store(store)

    assert result.dna_workflow is dna
    assert result.rna_workflow is rna


def test_missing_rule_version_is_rejected() -> None:
    testing = service()
    testing.rule_repository.document = None
    with pytest.raises(AppError, match="version was not found"):
        testing._rule_set("missing")


def test_search_limits_samples_to_rule_scope_and_returns_minimal_metadata() -> None:
    rows = [
        {
            "_id": "s1",
            "name": "Sample 1",
            "asp_id": "assay_1",
            "subpanel_id": "base",
            "environment": "production",
            "omics_layer": "dna",
        },
        {"_id": "s2", "case_id": "Case 2"},
        {"_id": "s3"},
    ]
    testing = service(rows=rows)

    result = testing.search_samples(
        document_id="rule",
        search="sample",
        match_subpanel=True,
        allowed_asp_ids=["assay_1"],
        allowed_environments=["production"],
        page=2,
        per_page=10,
    )

    assert [item["name"] for item in result["items"]] == ["Sample 1", "Case 2", "s3"]
    assert result["items"][1]["subpanel_id"] == "base"
    assert result["total"] == 3
    assert testing.sample_repository.call == {
        "asp_ids": ["assay_1"],
        "environments": ["production"],
        "subpanel_id": "base",
        "search_str": "sample",
        "page": 2,
        "per_page": 10,
        "ready_only": True,
    }


def test_search_supports_assay_only_and_superuser_scope() -> None:
    testing = service()
    testing.search_samples(
        document_id="rule",
        search="",
        match_subpanel=False,
        allowed_asp_ids=None,
        allowed_environments=None,
        page=1,
        per_page=20,
    )
    assert testing.sample_repository.call["subpanel_id"] is None


def test_search_rejects_rule_outside_user_assay_scope() -> None:
    with pytest.raises(AppError, match="outside your assigned scope"):
        service().search_samples(
            document_id="rule",
            search="",
            match_subpanel=False,
            allowed_asp_ids=["another_assay"],
            allowed_environments=[],
            page=1,
            per_page=20,
        )


@pytest.mark.parametrize("analyte", ["dna", "rna"])
def test_preview_uses_selected_rule_version_without_persistence(monkeypatch, analyte) -> None:
    document = _document()
    document = document.model_copy(
        update={"scope": document.scope.model_copy(update={"analyte": analyte})}
    )
    context = _context()
    context.sample.omics_layer = analyte
    evaluation = (
        ClinicalRuleEvaluator()
        .evaluate(
            context,
            document,
            reporting_analyses={"SNV"},
        )
        .model_dump(mode="json")
    )
    testing = service(document=document, evaluation=evaluation)
    monkeypatch.setattr(
        "api.application.reporting.clinical_rules.testing.get_formatted_assay_config",
        lambda sample, **kwargs: {"reporting": {"report_sections": ["SNV"]}},
    )

    result = testing.preview(
        document_id="rule",
        sample={"_id": "s1", "case_id": "Case 1", "asp_id": "assay_1"},
    )

    workflow = testing.dna_workflow if analyte == "dna" else testing.rna_workflow
    assert workflow.call["save"] == 0
    assert workflow.call["include_snapshot"] is False
    assert workflow.call["clinical_rule_only"] is True
    assert workflow.call["clinical_rule_condition_trace"] is False
    assert workflow.call["clinical_rule_override"].rule_set_id == "assay_1__base__sv"
    assert result["persisted"] is False
    assert result["sample"]["name"] == "Case 1"
    assert "Findings" in result["summary"]


def test_preview_can_request_detailed_condition_trace(monkeypatch) -> None:
    evaluation = (
        ClinicalRuleEvaluator()
        .evaluate(_context(), _document(), reporting_analyses={"SNV"})
        .model_dump(mode="json")
    )
    testing = service(evaluation=evaluation)
    monkeypatch.setattr(
        "api.application.reporting.clinical_rules.testing.get_formatted_assay_config",
        lambda sample, **kwargs: {"reporting": {"report_sections": ["SNV"]}},
    )

    testing.preview(
        document_id="rule",
        sample={"_id": "s1", "name": "Sample 1", "asp_id": "assay_1"},
        include_condition_trace=True,
    )

    assert testing.dna_workflow.call["clinical_rule_condition_trace"] is True


def test_preview_rejects_wrong_assay_and_missing_evaluation(monkeypatch) -> None:
    testing = service(evaluation=None)
    with pytest.raises(AppError, match="does not match"):
        testing.preview(document_id="rule", sample={"asp_id": "other"})

    monkeypatch.setattr(
        "api.application.reporting.clinical_rules.testing.get_formatted_assay_config",
        lambda sample, **kwargs: {},
    )
    with pytest.raises(AppError, match="did not produce"):
        testing.preview(
            document_id="rule",
            sample={"_id": "s1", "name": "Sample 1", "asp_id": "assay_1"},
        )

    failing = service(evaluation=ValueError("missing finding data"))
    with pytest.raises(AppError, match="does not satisfy"):
        failing.preview(
            document_id="rule",
            sample={"_id": "s1", "name": "Sample 1", "asp_id": "assay_1"},
        )


def test_explicit_version_evaluation_rejects_engine_and_analyte_mismatches() -> None:
    runtime = ClinicalRuleService(repository=object())
    context = _context()
    document = ClinicalRuleSetDoc.model_validate(_document())

    with pytest.raises(ValueError, match="requires engine version"):
        runtime.evaluate_document(
            rule_set=document.model_copy(update={"minimum_engine_version": 999}),
            context=context,
        )
    with pytest.raises(ValueError, match="analyte does not match"):
        runtime.evaluate_document(
            rule_set=document.model_copy(
                update={"scope": document.scope.model_copy(update={"analyte": "rna"})}
            ),
            context=context,
        )
