"""Runtime resolution and evaluation of published clinical report rules."""

from __future__ import annotations

from typing import Any

from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.facts import PreparedReportContext
from api.application.reporting.clinical_rules.validation import ENGINE_VERSION, content_hash
from api.config.constants import normalize_analysis_type
from api.contracts.schemas.clinical_rules import ClinicalRuleEvaluation, ClinicalRuleSetDoc


class ClinicalRuleService:
    """Resolve the explicitly bound active release and evaluate prepared facts."""

    def __init__(self, repository: Any, evaluator: ClinicalRuleEvaluator | None = None) -> None:
        self.repository = repository
        self.evaluator = evaluator or ClinicalRuleEvaluator()

    @classmethod
    def from_store(cls, store: Any) -> "ClinicalRuleService":
        return cls(store.clinical_rule_set_repository)

    def resolve(self, *, context: PreparedReportContext) -> ClinicalRuleSetDoc:
        rule_set_id = context.aspc.reporting.clinical_rule_set_id
        if not rule_set_id:
            raise ValueError("ASPC does not define reporting.clinical_rule_set_id")
        document = self.repository.get_active(rule_set_id)
        if document is None:
            raise ValueError(f"No active published clinical rule set exists for '{rule_set_id}'")
        rule_set = ClinicalRuleSetDoc.model_validate(document)
        if rule_set.minimum_engine_version > ENGINE_VERSION:
            raise ValueError(
                f"Clinical rule set requires engine version {rule_set.minimum_engine_version}"
            )
        if rule_set.scope.analyte != context.sample.omics_layer:
            raise ValueError("Clinical rule-set analyte does not match the report context")
        if rule_set.content_hash != content_hash(rule_set):
            raise ValueError("Published clinical rule-set content failed integrity validation")
        return rule_set

    @staticmethod
    def _report_sections(context: PreparedReportContext) -> set[str]:
        return {
            normalize_analysis_type(value)
            for value in context.aspc.reporting.report_sections
            if str(value or "").strip()
        }

    def evaluate(
        self,
        *,
        aspc: dict[str, Any],
        context: PreparedReportContext,
    ) -> ClinicalRuleEvaluation:
        _ = aspc
        rule_set = self.resolve(context=context)
        return self.evaluate_document(rule_set=rule_set, context=context)

    def evaluate_document(
        self,
        *,
        rule_set: ClinicalRuleSetDoc,
        context: PreparedReportContext,
        include_condition_trace: bool = False,
    ) -> ClinicalRuleEvaluation:
        """Evaluate an explicitly selected rule version against prepared report facts."""
        if rule_set.minimum_engine_version > ENGINE_VERSION:
            raise ValueError(
                f"Clinical rule set requires engine version {rule_set.minimum_engine_version}"
            )
        if rule_set.scope.analyte != context.sample.omics_layer:
            raise ValueError("Clinical rule-set analyte does not match the report context")
        report_sections = self._report_sections(context)
        undeclared = sorted(report_sections - set(rule_set.analysis_declarations))
        if undeclared:
            raise ValueError(
                "Clinical rule set does not declare every ASPC report section: "
                + ", ".join(undeclared)
            )
        return self.evaluator.evaluate(
            context,
            rule_set,
            reporting_analyses=report_sections,
            include_condition_trace=include_condition_trace,
        )


def rendered_summary(evaluation: ClinicalRuleEvaluation | None) -> str:
    """Flatten ordered rendered sections into report-ready Markdown text."""
    if evaluation is None:
        return ""
    paragraphs: list[str] = []
    for section, texts in evaluation.sections.items():
        if not texts:
            continue
        if evaluation.section_headings.get(section, True):
            paragraphs.append(f"## {section}")
        paragraphs.extend(texts)
    return "\n\n".join(paragraphs)
