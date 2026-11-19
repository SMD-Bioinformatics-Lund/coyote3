# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Durable ingest execution independent of task transport and persistence implementation."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, Protocol, cast

from coyote.application.common.observability import timed_operation
from coyote.application.ingest.failures import ingest_failure_message

logger = logging.getLogger(__name__)


class IngestJobRepository(Protocol):
    """Persistence port retaining fenced job claims and transaction completion."""

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Read the current durable job state.

        Args:
            job_id: Previously accepted job identifier.

        Returns:
            Retained job and lease metadata, or None if it does not exist.
        """
        ...

    def claim(self, job_id: str, *, lease_seconds: int) -> dict[str, Any] | None:
        """Claim an available job with an expiring exclusive lease.

        Args:
            job_id: Pending job or job whose previous lease expired.
            lease_seconds: Exclusive claim duration in seconds.

        Returns:
            Claimed job including its new lease token, or None if unavailable.
        """
        ...

    def complete(self, job_id: str, lease_token: str, result: dict[str, Any], session: Any) -> None:
        """Retain completion in the transaction that writes the ingested data.

        Args:
            job_id: Claimed durable job identifier.
            lease_token: Fencing token of the worker attempting completion.
            result: Successful ingest result retained for duplicate delivery.
            session: The write transaction; None for an explicitly nontransactional host.

        Raises:
            RuntimeError: The claim has been replaced and cannot complete.
        """
        ...

    def fail(self, job_id: str, lease_token: str, *, retryable: bool, error: str) -> bool:
        """Record failure only for the current lease.

        Args:
            job_id: Claimed durable job identifier.
            lease_token: Fencing token of the worker reporting failure.
            retryable: Whether the job should remain eligible for later execution.
            error: Safe failure explanation without source payload or credentials.

        Returns:
            True if the failure was retained; False if the claim no longer owns the job.
        """
        ...


class IngestJobRunner:
    """Execute retained jobs using explicit authorization, persistence and host ports.

    The executor must revalidate managed credentials and complete through the supplied
    transaction callback. Failure classification and cleanup are host integrations;
    the runner owns duplicate delivery, fencing and committed-result recovery.
    """

    def __init__(
        self,
        *,
        repository: IngestJobRepository,
        execute: Callable[..., dict[str, Any]],
        family_enabled: Callable[[str], bool],
        retryable_error: Callable[[Exception], bool],
        audit: Callable[..., None],
        notify_failure: Callable[..., None],
        cleanup_staging: Callable[[str], None],
        lease_seconds: int,
        observer: Callable[..., None] | None = None,
    ) -> None:
        """Bind the host ports used while claiming and completing retained jobs.

        Args:
            repository: Fenced claims, completion and failure persistence.
            execute: Authorized executor accepting a transaction completion callback.
            family_enabled: Live task-control lookup by task family.
            retryable_error: Classifier for temporary persistence or process failures.
            audit: Best-effort traceability event delivery.
            notify_failure: Recipient notification delivery for permanent failures.
            cleanup_staging: Remove upload staging after confirmed completion.
            lease_seconds: Claim duration, including the host's task timeout margin.
            observer: Optional operation timing observer.
        """
        self.repository = repository
        self.execute = execute
        self.family_enabled = family_enabled
        self.retryable_error = retryable_error
        self.audit = audit
        self.notify_failure = notify_failure
        self.cleanup_staging = cleanup_staging
        self.lease_seconds = lease_seconds
        self.observer = observer

    def run(self, job_id: str) -> dict[str, Any]:
        """Claim a durable ingest job and record completion with its data writes.

        Args:
            job_id: Identifier of a previously submitted job.

        Returns:
            Ingest result, a busy status when another worker owns the
            lease, or a disabled status when the job's task family is disabled.
            Previously successful jobs return their stored result.

        Raises:
            ValueError: The job does not exist or has already failed permanently.

        Notes:
            Completion is recorded through the ingest service's transaction callback.
            Execution failures update retry state and propagate unless a committed
            result is found. Successful jobs remove their staging directory and emit
            a best-effort audit event.
        """
        repository = self.repository
        existing = repository.get(job_id)
        if existing is None:
            raise ValueError("Ingest job not found")
        family = "sample_ingest" if existing["kind"] == "sample_bundle" else "collection_writes"
        if not self.family_enabled(family):
            return {"status": "disabled", "task_family": family}
        if existing["state"] == "succeeded":
            if existing.get("staging_dir"):
                self.cleanup_staging(existing["staging_dir"])
            return cast(dict[str, Any], existing["result"])
        if existing["state"] == "failed":
            raise ValueError(existing.get("error") or "Ingest job failed")
        job = repository.claim(job_id, lease_seconds=self.lease_seconds)
        if job is None:
            return {"status": "busy", "job_id": job_id}
        self.audit(
            "ingest.bundle.started",
            "Ingest worker claimed job",
            actor=job.get("submitted_by"),
            resource_type="ingest",
            resource_id=job_id,
            metadata={
                "task_id": job_id,
                "attempt": job.get("attempts"),
                "source": "celery",
                "credential_id": job.get("credential_id"),
                "credential_owner": job.get("credential_owner"),
            },
        )
        try:
            with timed_operation("ingest.sample_bundle", observer=self.observer, task_id=job_id):

                def completion(result: dict[str, Any], session: Any) -> None:
                    """Complete the leased job within the ingest transaction.

                    Args:
                        result: Ingest result to persist for duplicate delivery.
                        session: Persistence transaction owning the corresponding data writes.
                    """
                    repository.complete(job_id, job["lease_token"], result, session)

                if job["kind"] == "sample_bundle":
                    source_payload = dict(job["source_payload"])
                    for warning in source_payload.pop("_ingest_warnings", []):
                        self.audit(
                            "ingest.bundle.files_ignored",
                            warning,
                            severity="warning",
                            outcome="warning",
                            actor=job.get("submitted_by"),
                            metadata={"task_id": job_id},
                        )
                result = self.execute(job, record_completion=completion)
        except Exception as exc:
            retryable = self.retryable_error(exc)
            error = ingest_failure_message(exc, retryable=retryable)
            logger.exception("Ingest task %s failed: %s", job_id, error)
            recorded_failure = repository.fail(
                job_id, job["lease_token"], retryable=retryable, error=error
            )
            committed = repository.get(job_id)
            if committed is not None and committed["state"] == "succeeded":
                result = committed["result"]
            elif not recorded_failure:
                return {"status": "busy", "job_id": job_id}
            else:
                self.audit(
                    "ingest.bundle.failed",
                    f"Ingest attempt failed: {error}",
                    severity="error",
                    outcome="failure",
                    actor=job.get("submitted_by"),
                    metadata={
                        "task_id": job_id,
                        "attempt": job.get("attempts"),
                        "source": "celery",
                        "retryable": retryable,
                        "error": error,
                    },
                )
                if not retryable and job.get("submitted_by"):
                    try:
                        self.notify_failure(
                            audience="users",
                            recipients=[job.get("credential_owner") or job["submitted_by"]],
                            tone="error",
                            category="application",
                            title="Ingest failed",
                            message=f"{error}\nTask ID: {job_id}",
                            source="Ingest workspace",
                            created_by="system",
                            severity="warning",
                            resource={"type": "ingest", "id": job_id},
                        )
                    except Exception:
                        logger.exception(
                            "Could not deliver failure notification for ingest task %s", job_id
                        )
                raise
        if job.get("staging_dir"):
            self.cleanup_staging(job["staging_dir"])
        try:
            self.audit(
                "ingest.bundle.succeeded",
                "Sample bundle ingested",
                actor=job.get("submitted_by"),
                resource_type="sample",
                resource_id=str(result.get("sample_id", "")),
                resource_name=str(result.get("sample_name", "")),
                metadata={
                    "task_id": job_id,
                    "attempt": job.get("attempts"),
                    "source": "celery",
                    "counts": result.get("counts") or result.get("data_counts"),
                },
            )
        except Exception:
            logger.exception("Ingest committed; audit delivery failed")
        return result
