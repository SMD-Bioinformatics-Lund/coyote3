"""SDK entry point for trusted workers executing durable ingestion jobs."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from coyote3.application.ingest.jobs import sample_entry_source
from coyote3.application.operations.runtime import ApplicationRuntime

if TYPE_CHECKING:
    from coyote3.application.ingest.service import InternalIngestService


class IngestJobExecution:
    """Execute stored jobs under a worker identity while retaining original attribution."""

    def __init__(self, runtime: ApplicationRuntime, service: InternalIngestService) -> None:
        """Bind worker authentication and the existing transactional ingest workflow."""
        self._runtime, self._service = runtime, service

    def execute(
        self, job: dict[str, Any], *, record_completion: Callable[..., None]
    ) -> dict[str, Any]:
        """Execute a claimed durable job without moving its completion outside the transaction.

        Args:
            job: Trusted repository-loaded job, including kind, payload and original submitter.
                Never accept this object from an unauthenticated transport.
            record_completion: Host callback recording the lease result in the ingest transaction.

        Returns:
            Existing ingest result after writes and job completion commit together.

        Raises:
            AppError: The worker identity lacks the ingestion capability.
            ValueError: The durable job kind is unsupported or ingestion validation fails.
        """

        def run(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Dispatch only supported stored job kinds, retaining their original service arguments."""
            payload = dict(job["source_payload"])
            if job["kind"] == "sample_bundle":
                payload.pop("_ingest_warnings", None)
                return dict(
                    self._service.ingest_sample_bundle(
                        payload,
                        allow_update=job["update_existing"],
                        increment=job["increment"],
                        ingested_by=job["submitted_by"],
                        ingest_source=sample_entry_source(job),
                        record_completion=record_completion,
                    )
                )
            operations = {
                "insert_document": self._service.insert_collection_document,
                "insert_documents": self._service.insert_collection_documents,
                "upsert_document": self._service.upsert_collection_document,
            }
            if job["kind"] not in operations:
                raise ValueError("Unsupported durable ingestion job kind")
            payload["ingested_by"] = job["submitted_by"]
            return dict(operations[job["kind"]](**payload, record_completion=record_completion))

        return self._runtime.execute("ingest.execute_job", ("internal.ingest:manage",), run)
