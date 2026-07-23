"""Explicit publication service for repository-authored clinical rules."""

from __future__ import annotations

from pathlib import Path

from api.application.reporting.clinical_rules.compiler import ClinicalRuleCompiler
from api.contracts.schemas.clinical_rules import ClinicalRuleReleaseDoc


class ClinicalRulePublisher:
    """Validate and publish YAML rule sets without startup synchronization."""

    def __init__(self, repository, compiler: ClinicalRuleCompiler | None = None) -> None:
        self.repository = repository
        self.compiler = compiler or ClinicalRuleCompiler()

    def publish(self, source_path: str | Path, *, published_by: str) -> ClinicalRuleReleaseDoc:
        """Publish one source as an immutable release."""
        path = Path(source_path)
        source = self.compiler.load(path)
        return self.repository.publish(
            source=source,
            content_hash=self.compiler.content_hash(source),
            source_path=path.as_posix(),
            published_by=published_by,
        )
