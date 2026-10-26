"""Runtime resolution and evaluation of published clinical report rules."""

from __future__ import annotations

from typing import Any

from coyote3.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from coyote3.application.reporting.clinical_rules.facts import PreparedReportContext
from coyote3.application.reporting.clinical_rules.resolution import (
    MissingClinicalRuleSet,
    record_clinical_rules,
    resolve_published_rule_set,
)
from coyote3.application.reporting.clinical_rules.validation import (
    REPORT_METADATA_SECTIONS,
)
from coyote3.config.constants import normalize_analysis_type
from coyote3.contracts.schemas.clinical_rules import ClinicalRuleEvaluation, ClinicalRuleSetDoc


class ClinicalRuleService:
    """Resolve a published release by scope and evaluate prepared facts."""

    def __init__(
        self,
        repository: Any,
        evaluator: ClinicalRuleEvaluator | None = None,
        *,
        profiles: Any = None,
        assays: Any = None,
    ) -> None:
        """Configure release lookup and rule evaluation.

        Args:
            repository: Provides active published rule documents by assay.
            evaluator: Evaluation engine; None creates ClinicalRuleEvaluator.
            profiles: Published scoped clinical-rule profiles, or None when none are configured.
            assays: Current assay registry used to match clinical profile bindings.
        """
        self.repository = repository
        self.evaluator = evaluator or ClinicalRuleEvaluator()
        self.profiles, self.assays = profiles, assays

    @classmethod
    def from_store(cls, store: Any) -> "ClinicalRuleService":
        """Bind runtime evaluation to the store's rule repository.

        Args:
            store: Provider of clinical rule, published profile and assay repositories.

        Returns:
            Service with the default evaluator.
        """
        return cls(
            store.clinical_rule_set_repository,
            profiles=store.configuration_profile_repository,
            assays=store.assay_panel_repository,
        )

    def resolve(self, *, context: PreparedReportContext) -> ClinicalRuleSetDoc:
        """Resolve and integrity-check the sample scope's active release.

        Args:
            context: Report facts providing sample scope, analyte and reporting language.

        Returns:
            Parsed active rule version with a verified canonical content hash.

        Raises:
            ValueError: Release is absent or ambiguous, schema version is
                unsupported, analyte differs, or the content hash does not match.
            AppError: Published clinical profiles are ambiguous, corrupt or incompatible.
        """
        release = resolve_published_rule_set(
            self.repository,
            asp_id=context.sample.asp_id,
            diagnosis_id=context.sample.diagnosis_id,
            analyte=context.sample.asp_category,
            language=context.aspc.reporting.language,
        )
        from coyote3.application.resources.configuration_profiles import (
            compile_profile_rules,
            compile_profiles,
        )

        configuration = {
            "asp_id": context.sample.asp_id,
            "diagnosis_id": context.sample.diagnosis_id,
            "environment": context.sample.environment,
            "clinical_rule_release": release.model_dump(mode="python", by_alias=True),
        }
        panel = self.assays.get_asp(context.sample.asp_id) if self.assays is not None else None
        if self.profiles is not None:
            if not panel:
                raise ValueError("Clinical rule profiles require a registered assay")
            configuration["asp_group"] = panel["asp_group"]
            compile_profiles(configuration, panel, self.profiles, kinds={"clinical_rules"})
            compile_profile_rules(configuration)
        record_clinical_rules(
            release.rule_set_id,
            {
                "rule_set": configuration["clinical_rule_release"],
                "base": release.model_dump(mode="python", by_alias=True),
                "profiles": configuration.get("profile_sources", []),
            },
        )
        return ClinicalRuleSetDoc.model_validate(configuration["clinical_rule_release"])

    def annotation_tumor_type(self, *, aspc: dict, sample: dict) -> str | None:
        """Read automatic-annotation terminology from the current scoped DNA publication.

        Args:
            aspc: Sample configuration supplying the reporting language.
            sample: Sample supplying the assay, diagnosis and analyte scope.

        Returns:
            Configured tumor-type wording, or None when automatic annotation is not configured.

        Raises:
            ValueError: Release resolution/integrity fails or automatic Swedish text
                is requested for another reporting language.
        """
        if sample.get("asp_category") != "dna":
            raise ValueError("Automatic variant annotation requires a DNA configuration")
        try:
            release = resolve_published_rule_set(
                self.repository,
                asp_id=sample["asp_id"],
                diagnosis_id=sample.get("diagnosis_id") or "base",
                analyte="dna",
                language=aspc.get("reporting", {}).get("language", "sv"),
            )
        except MissingClinicalRuleSet:
            return None
        if release.scope.analyte != "dna":
            raise ValueError("Automatic variant annotation requires a DNA configuration")
        language = release.scope.language
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
    ) -> ClinicalRuleEvaluation | None:
        """Evaluate current published scope rules against the sample's configuration settings.

        Args:
            aspc: Exact sample configuration supplying reporting settings.
            context: Prepared facts and reporting configuration.

        Returns:
            Rendered sections, provenance and traces, or None when no publication exists.

        Raises:
            ValueError: Release resolution fails, report analyses are undeclared,
                or the evaluator cannot render the rules.
        """
        if (
            aspc.get("asp_id") != context.sample.asp_id
            or aspc.get("environment") != context.sample.environment
            or aspc.get("aspc_id") != context.aspc.aspc_id
        ):
            raise ValueError("Report context does not match its pinned configuration")
        try:
            rule_set = self.resolve(context=context)
        except MissingClinicalRuleSet:
            return None
        return self.evaluate_document(rule_set=rule_set, context=context)

    def evaluate_document(
        self,
        *,
        rule_set: ClinicalRuleSetDoc,
        context: PreparedReportContext,
        include_condition_trace: bool = False,
    ) -> ClinicalRuleEvaluation:
        """Evaluate an explicitly selected rule version against prepared report facts."""
        if rule_set.scope.analyte != context.sample.asp_category:
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
