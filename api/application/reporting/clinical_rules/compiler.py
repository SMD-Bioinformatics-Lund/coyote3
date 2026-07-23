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
from api.contracts.schemas.clinical_rules import ClinicalRuleSetSource

TEMPLATE_ROOTS = frozenset(
    {"sample", "asp", "aspc", "applied_gene_lists", "finding", "biomarkers", "aggregates"}
)


class ClinicalRuleCompiler:
    """Compile repository-authored rule files into canonical release content."""

    def __init__(self) -> None:
        self.environment = clinical_template_environment()

    def load(self, source_path: str | Path) -> ClinicalRuleSetSource:
        """Load and validate one YAML source file."""
        path = Path(source_path)
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Clinical rule source must be a mapping: {path}")
        source = ClinicalRuleSetSource.model_validate(payload)
        self.validate(source)
        return source

    def validate(self, source: ClinicalRuleSetSource) -> None:
        """Validate facts and restricted template variables."""
        for fact in source.rule_set.required_facts:
            validate_fact_path(fact)
        for rule in source.rules:
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
