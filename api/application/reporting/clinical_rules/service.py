"""Runtime orchestration for published clinical reporting rules."""

from __future__ import annotations

from typing import Any

from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.facts import PreparedReportContext
from api.application.reporting.clinical_rules.registry import validate_fact_path
from api.contracts.schemas.clinical_rules import ClinicalRuleEvaluation


class ClinicalRuleService:
    """Resolve ASPC-bound releases and evaluate prepared report facts."""

    def __init__(self, repository, evaluator: ClinicalRuleEvaluator | None = None) -> None:
        self.repository = repository
        self.evaluator = evaluator or ClinicalRuleEvaluator()

    @classmethod
    def from_store(cls, store) -> "ClinicalRuleService":
        return cls(store.clinical_rule_set_repository)

    @staticmethod
    def _scope_matches(context: PreparedReportContext, scope) -> bool:
        sample = context.sample
        aspc = context.aspc
        return (
            scope.analyte == sample.omics_layer
            and scope.assay_id == sample.assay
            and scope.subpanel_id == aspc.subpanel_id
        )

    @staticmethod
    def _fact_exists(context: PreparedReportContext, path: str) -> bool:
        validate_fact_path(path)
        value: Any = context.evaluation_scope()
        for part in path.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
                continue
            return False
        return value is not None

    def evaluate_bound_release(
        self,
        *,
        aspc: dict[str, Any],
        context: PreparedReportContext,
    ) -> ClinicalRuleEvaluation | None:
        """Evaluate the exact immutable release referenced by the ASPC."""
        aspc_doc = aspc.model_dump(mode="python") if hasattr(aspc, "model_dump") else aspc
        reference = (aspc_doc.get("reporting") or {}).get("clinical_rule_release")
        if not reference:
            return None
        release = self.repository.get_referenced_release(reference)
        if release is None:
            raise ValueError("The ASPC references a clinical rule release that does not exist")
        if release.status != "active":
            raise ValueError("The ASPC references a clinical rule release that is not active")
        if not self._scope_matches(context, release.source.rule_set.scope):
            raise ValueError("The clinical rule release scope does not match the report context")
        missing = [
            fact
            for fact in release.source.rule_set.required_facts
            if not self._fact_exists(context, fact)
        ]
        if missing:
            raise ValueError(
                "The prepared report context is missing required clinical facts: "
                + ", ".join(sorted(missing))
            )
        return self.evaluator.evaluate(context, release)


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
