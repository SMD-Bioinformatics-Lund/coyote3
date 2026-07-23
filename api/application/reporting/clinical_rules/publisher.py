"""Explicit publication service for repository-authored clinical rules."""

from __future__ import annotations

from pathlib import Path

from api.application.reporting.clinical_rules.compiler import ClinicalRuleCompiler
from api.contracts.schemas.clinical_rules import ClinicalRuleReleaseDoc


class ClinicalRulePublisher:
    """Validate and publish active YAML rule sets without startup synchronization."""

    def __init__(self, repository, compiler: ClinicalRuleCompiler | None = None) -> None:
        self.repository = repository
        self.compiler = compiler or ClinicalRuleCompiler()

    def publish(self, source_path: str | Path, *, published_by: str) -> ClinicalRuleReleaseDoc:
        """Publish one active source as an immutable release."""
        path = Path(source_path)
        source = self.compiler.load(path)
        if source.rule_set.status != "active":
            raise ValueError(
                f"Rule set '{source.rule_set.rule_set_id}' has status "
                f"'{source.rule_set.status}'; only active sources can be published."
            )
        validation = source.rule_set.validation
        if validation.approval_status not in {"inherited", "approved"}:
            raise ValueError("Clinical rule publication requires inherited or explicit approval.")
        if not validation.approval_reference or not validation.golden_case_ids:
            raise ValueError(
                "Clinical rule publication requires an approval reference and golden cases."
            )
        return self.repository.publish(
            source=source,
            content_hash=self.compiler.content_hash(source),
            source_path=path.as_posix(),
            published_by=published_by,
        )
