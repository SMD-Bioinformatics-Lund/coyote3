"""Runtime orchestration for published clinical reporting rules."""

from __future__ import annotations

from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.facts import PreparedReportContext
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
    def _scope_matches(context: PreparedReportContext, rule_set) -> bool:
        sample = context.sample
        aspc = context.aspc
        return (
            rule_set.analyte == sample.omics_layer
            and rule_set.assay_id == sample.assay
            and rule_set.subpanel_id == aspc.subpanel_id
        )

    def evaluate_bound_release(
        self,
        *,
        aspc: dict,
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
        if not self._scope_matches(context, release.source.rule_set):
            raise ValueError("The clinical rule release scope does not match the report context")
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
