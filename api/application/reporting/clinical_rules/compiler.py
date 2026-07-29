"""Load, validate, and deterministically compile authored YAML rules."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from jinja2 import meta

from api.application.reporting.clinical_rules.registry import validate_fact_path
from api.application.reporting.clinical_rules.templating import clinical_template_environment
from api.config.constants import DNA_ANALYSIS_TYPE_OPTIONS, RNA_ANALYSIS_TYPE_OPTIONS
from api.contracts.schemas.clinical_rules import ClinicalRuleSetSource

TEMPLATE_ROOTS = frozenset(
    {"sample", "asp", "aspc", "applied_gene_lists", "finding", "biomarkers", "aggregates"}
)


class ClinicalRuleCompiler:
    """Compile repository-authored rule files into canonical static content."""

    def __init__(self) -> None:
        self.environment = clinical_template_environment()

    def load(self, source_path: str | Path) -> ClinicalRuleSetSource:
        """Load and validate one YAML source file."""
        path = Path(source_path)
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Clinical rule source must be a mapping: {path}")
        source = ClinicalRuleSetSource.model_validate(payload)
        self._validate_repository_path(path, source)
        self.validate(source)
        return source

    def discover(self, rules_root: str | Path) -> list[Path]:
        """Return all assay/subpanel rule sources in deterministic order."""
        return sorted(Path(rules_root).glob("*/*.yaml"))

    @staticmethod
    def _validate_repository_path(path: Path, source: ClinicalRuleSetSource) -> None:
        """Require repository paths to mirror the exact rule scope."""
        roots = [parent for parent in path.parents if parent.name == "clinical_reporting_rules"]
        if not roots:
            return
        relative = path.relative_to(roots[0])
        if len(relative.parts) != 2:
            raise ValueError(
                "Clinical rule sources must use clinical_reporting_rules/"
                "<asp_id>/<subpanel_id>.yaml"
            )
        assay_id = relative.parts[0]
        subpanel_id = relative.name.split(".", 1)[0]
        rule_set = source.rule_set
        if (rule_set.asp_id, rule_set.subpanel_id) != (assay_id, subpanel_id):
            raise ValueError(
                "Clinical rule source path does not match its assay/subpanel scope: "
                f"{assay_id}/{subpanel_id} != {rule_set.asp_id}/{rule_set.subpanel_id}"
            )

    def validate(self, source: ClinicalRuleSetSource) -> None:
        """Validate facts and restricted template variables."""
        allowed_analyses = (
            set(DNA_ANALYSIS_TYPE_OPTIONS)
            if source.rule_set.analyte == "dna"
            else set(RNA_ANALYSIS_TYPE_OPTIONS)
        )
        invalid_analyses = sorted(set(source.analyses) - allowed_analyses)
        if invalid_analyses:
            raise ValueError(
                f"Rule set uses analyses unavailable for {source.rule_set.analyte}: "
                f"{invalid_analyses}"
            )
        rules = list(source.document_rules)
        for block in source.analyses.values():
            rules.extend(block.rules)
        for rule in rules:
            for condition in rule.when:
                validate_fact_path(condition.fact)
            ast = self.environment.parse(rule.template)
            undeclared = meta.find_undeclared_variables(ast)
            unsupported = sorted(undeclared - TEMPLATE_ROOTS)
            if unsupported:
                raise ValueError(
                    f"Rule '{rule.rule_id}' uses unsupported template variables: {unsupported}"
                )

    @staticmethod
    def canonical_payload(source: ClinicalRuleSetSource) -> dict[str, Any]:
        """Return the stable JSON-compatible source representation."""
        return source.model_dump(mode="json", exclude_none=True)

    def content_hash(self, source: ClinicalRuleSetSource) -> str:
        """Return the SHA-256 hash of canonical compiled content."""
        canonical = json.dumps(
            self.canonical_payload(source),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()
