"""Runtime resolution and evaluation of published clinical report rules."""

from __future__ import annotations

from typing import Any

from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.facts import PreparedReportContext
from api.application.reporting.clinical_rules.resolution import resolve_published_rule_set
from api.application.reporting.clinical_rules.validation import (
    REPORT_METADATA_SECTIONS,
)
from api.config.constants import normalize_analysis_type
from api.contracts.schemas.clinical_rules import ClinicalRuleEvaluation, ClinicalRuleSetDoc


class ClinicalRuleService:
    """Resolve a published release by scope and evaluate prepared facts."""

    def __init__(self, repository: Any, evaluator: ClinicalRuleEvaluator | None = None) -> None:
        """Configure release lookup and rule evaluation.

        Args:
            repository: Provides active published rule documents by assay.
            evaluator: Evaluation engine; None creates ClinicalRuleEvaluator.
        """
        self.repository = repository
        self.evaluator = evaluator or ClinicalRuleEvaluator()

    @classmethod
    def from_store(cls, store: Any) -> "ClinicalRuleService":
        """Bind runtime evaluation to the store's rule repository.

        Args:
            store: Provider of clinical_rule_set_repository.

        Returns:
            Service with the default evaluator.
        """
        return cls(store.clinical_rule_set_repository)

    def resolve(self, *, context: PreparedReportContext) -> ClinicalRuleSetDoc:
        """Resolve and integrity-check the sample scope's active release.

        Args:
            context: Report facts providing sample scope, analyte and reporting language.

        Returns:
            Parsed active rule version with a verified canonical content hash.

        Raises:
            ValueError: Release is absent or ambiguous, schema version is
                unsupported, analyte differs, or the content hash does not match.
        """
        return resolve_published_rule_set(
            self.repository,
            asp_id=context.sample.asp_id,
            subpanel_id=context.sample.subpanel_id,
            analyte=context.sample.omics_layer,
            language=context.aspc.reporting.language,
        )

    def annotation_tumor_type(self, *, asp_id: str, subpanel_id: str, language: str) -> str | None:
        """Read approved automatic-annotation terminology from the scoped DNA release.

        Args:
            asp_id: Sample's assay identifier.
            subpanel_id: Sample's resolved interpretation scope, with assay Base fallback.
            language: ASPC reporting language. The existing automatic sentence supports sv.

        Returns:
            Configured tumor-type wording, or None when automatic annotation is not configured.

        Raises:
            ValueError: Release resolution/integrity fails or automatic Swedish text
                is requested for another reporting language.
        """
        release = resolve_published_rule_set(
            self.repository,
            asp_id=asp_id,
            subpanel_id=subpanel_id,
            analyte="dna",
            language=language,
        )
        value = release.terminology.get("automatic_annotation_tumor_type")
        if value and language != "sv":
            raise ValueError(
                "Automatic Tier III sentence generation currently requires Swedish reporting rules"
            )
        return value

    @staticmethod
    def _report_sections(context: PreparedReportContext) -> set[str]:
        """Canonicalize nonblank analysis names from prepared reporting settings.

        Args:
            context: Facts containing the ASPC report section list.

        Returns:
            Distinct normalized analysis names.
        """
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
        """Resolve the scoped release and evaluate the prepared reporting sections.

        Args:
            aspc: Accepted but unused; configuration is read from context.aspc.
            context: Prepared facts and reporting configuration.

        Returns:
            Rendered sections, source provenance, and rule decision traces.

        Raises:
            ValueError: Release resolution fails, report analyses are undeclared,
                or the evaluator cannot render the rules.
        """
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
        if section in REPORT_METADATA_SECTIONS:
            continue
        if not texts:
            continue
        if evaluation.section_headings.get(section, True):
            paragraphs.append(f"## {section}")
        paragraphs.extend(texts)
    return "\n\n".join(paragraphs)
