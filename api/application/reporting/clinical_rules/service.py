"""Static YAML rule-source selection and evaluation."""

from __future__ import annotations

from pathlib import Path

from api.application.reporting.clinical_rules.compiler import ClinicalRuleCompiler
from api.application.reporting.clinical_rules.evaluator import ClinicalRuleEvaluator
from api.application.reporting.clinical_rules.facts import PreparedReportContext
from api.config.constants import SUBPANEL_BASE_ID, normalize_analysis_type
from api.config.paths import CLINICAL_REPORTING_RULES_DIR
from api.contracts.schemas.clinical_rules import ClinicalRuleEvaluation, ClinicalRuleSetSource


class ClinicalRuleService:
    """Resolve repository-owned rules by stable ASP and subpanel identifiers."""

    def __init__(
        self,
        *,
        rules_root: str | Path = CLINICAL_REPORTING_RULES_DIR,
        compiler: ClinicalRuleCompiler | None = None,
        evaluator: ClinicalRuleEvaluator | None = None,
    ) -> None:
        self.rules_root = Path(rules_root)
        self.compiler = compiler or ClinicalRuleCompiler()
        self.evaluator = evaluator or ClinicalRuleEvaluator()

    @classmethod
    def from_store(cls, _store) -> "ClinicalRuleService":
        """Create the static service; report rules do not depend on MongoDB."""
        return cls()

    def _source_paths(self, *, asp_id: str, subpanel_id: str) -> list[Path]:
        directory = self.rules_root / asp_id
        requested = str(subpanel_id or SUBPANEL_BASE_ID).strip() or SUBPANEL_BASE_ID
        paths = [directory / f"{requested}.yaml"]
        if requested != SUBPANEL_BASE_ID:
            paths.append(directory / f"{SUBPANEL_BASE_ID}.yaml")
        return paths

    def resolve(self, *, context: PreparedReportContext) -> tuple[ClinicalRuleSetSource, Path]:
        """Load the exact subpanel file or that ASP's complete ``base.yaml`` fallback."""
        asp_id = str(context.asp.asp_id or context.sample.assay).strip()
        subpanel_id = str(context.aspc.subpanel_id or SUBPANEL_BASE_ID).strip()
        for source_path in self._source_paths(asp_id=asp_id, subpanel_id=subpanel_id):
            if not source_path.is_file():
                continue
            source = self.compiler.load(source_path)
            if source.rule_set.analyte != context.sample.omics_layer:
                raise ValueError("Clinical rule source analyte does not match the report context")
            if source.rule_set.asp_id != asp_id:
                raise ValueError("Clinical rule source ASP does not match the report context")
            return source, source_path
        raise ValueError(
            "No clinical rule source exists for ASP "
            f"'{asp_id}' and subpanel '{subpanel_id}', including base.yaml fallback"
        )

    @staticmethod
    def _reporting_analyses(context: PreparedReportContext) -> set[str]:
        return {
            normalize_analysis_type(value)
            for value in context.aspc.reporting.analysis
            if str(value or "").strip()
        }

    def evaluate(
        self,
        *,
        aspc: dict,
        context: PreparedReportContext,
    ) -> ClinicalRuleEvaluation:
        """Evaluate the selected static source against one prepared report result."""
        _ = aspc
        source, source_path = self.resolve(context=context)
        reporting_analyses = self._reporting_analyses(context)
        undeclared = sorted(reporting_analyses - set(source.analyses))
        if undeclared:
            raise ValueError(
                "Clinical rule source does not declare every ASPC reporting analysis: "
                + ", ".join(undeclared)
            )
        return self.evaluator.evaluate(
            context,
            source,
            source_path=source_path.relative_to(self.rules_root.parent),
            content_hash=self.compiler.content_hash(source),
            reporting_analyses=reporting_analyses,
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
