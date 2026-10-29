"""SDK operation for recording correlated synchronous ingestion attempts."""

from __future__ import annotations

import logging
from time import monotonic
from typing import Any
from uuid import uuid4

from coyote3.application.audit.service import AuditService
from coyote3.domain.exceptions import AppError


class IngestionAuditAttempt:
    """Record an attempt without changing ingestion or acknowledgement semantics."""

    def __init__(
        self,
        audit: AuditService | None,
        *,
        actor: Any,
        source: str,
        manifest: str | None = None,
        update_existing: bool = False,
        increment: bool = False,
    ) -> None:
        """Start a correlated attempt using authenticated identity and non-secret options.

        Args:
            audit: Configured durable audit service, or None when unavailable.
            actor: Authenticated submitting user or machine identity.
            source: Entry path label, such as api or upload.
            manifest: Uploaded filename when available; no file contents are retained.
            update_existing: Whether replacement of an existing sample was requested.
            increment: Whether allocation of a new suffixed sample was requested.
        """
        self.audit = audit
        self.actor = actor
        self.source = source
        self.started = monotonic()
        self.metadata: dict[str, Any] = {
            "attempt_id": uuid4().hex,
            "source": source,
            "manifest": manifest,
            "update_existing": update_existing,
            "increment": increment,
        }
        self._record("started", "Ingestion started")

    def _record(
        self,
        stage: str,
        message: str,
        *,
        result: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        """Append a retained event; audit delivery failure never retries committed work."""
        if self.audit is None:
            return
        result = result or {}
        metadata = {**self.metadata, "stage": stage}
        if stage != "started":
            metadata["duration_ms"] = round((monotonic() - self.started) * 1000)
        if error is not None:
            metadata.update(error=str(error), error_type=type(error).__name__)
        if result:
            metadata["counts"] = result.get("counts") or result.get("data_counts")
        try:
            self.audit.record(
                f"ingest.attempt.{stage}",
                message,
                category="data",
                severity="error" if error else "info",
                outcome="failure" if error else "success",
                actor=self.actor,
                resource_type="sample" if result.get("sample_id") else "ingest",
                resource_id=str(result.get("sample_id") or self.metadata["attempt_id"]),
                resource_name=result.get("sample_name"),
                tags=["ingest", self.source],
                metadata=metadata,
                retention_class="traceability",
            )
        except Exception:
            logging.getLogger(__name__).exception("Ingestion audit delivery failed")

    def succeeded(self, result: dict[str, Any]) -> None:
        """Record success only after ingestion returns its committed sample result."""
        self._record("succeeded", "Ingestion committed", result=result)

    def failed(self, error: Exception) -> None:
        """Distinguish known rejections from exceptions with an uncertain commit outcome."""
        known = isinstance(error, (ValueError, FileNotFoundError, UnicodeDecodeError, AppError))
        self._record(
            "failed" if known else "unconfirmed",
            "Ingestion rejected" if known else "Ingestion outcome needs reconciliation",
            error=error,
        )
