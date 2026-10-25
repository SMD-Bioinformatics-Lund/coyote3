"""Authenticated sample ingestion retaining the existing transaction boundary."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, Protocol

from coyote3.application.ingest.jobs import job_status_payload, submit_ingest_job
from coyote3.application.operations.ingest_permissions import (
    enforce_collection_permission,
    enforce_sample_ingest_permission,
)
from coyote3.application.operations.models import IngestResult
from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.domain.common.errors import api_error

if TYPE_CHECKING:
    from coyote3.application.ingest.service import InternalIngestService
    from coyote3.application.ingest.upload_bundle import BinaryUpload


class IngestJobs(Protocol):
    """Durable job acceptance and status independent of the storage provider."""

    def submit(self, **submission: Any) -> str:
        """Persist one validated job and return its durable identifier."""
        ...

    def get(self, job_id: str) -> dict[str, Any] | None:
        """Return a retained job, or None when the identifier does not exist."""
        ...


class IngestSubmissionServices:
    """Host-owned durable acceptance and worker notification capabilities."""

    def __init__(
        self, *, jobs: Callable[[], IngestJobs], publish: Callable[[str, str], None], queue: str
    ) -> None:
        """Bind durable jobs and the fixed ingest task queue.

        Args:
            jobs: Repository implementing durable job acceptance and lookup.
            publish: Publishes a supported job kind and its retained identifier.
            queue: Configured ingest queue name returned with acceptance metadata.
        """
        self.jobs, self.publish, self.queue = jobs, publish, queue


class Ingestion:
    """Execute sample-bundle use cases under a current ingestion grant."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        service: Callable[[], InternalIngestService],
        submission: IngestSubmissionServices,
    ) -> None:
        """Bind authenticated execution and the transactional ingestion service."""
        self._runtime, self._service = runtime, service
        self._submission = submission

    def sample_bundle(
        self,
        payload: dict[str, Any],
        *,
        allow_update: bool = False,
        increment: bool = False,
        source: Literal["api", "upload"] = "api",
    ) -> IngestResult:
        """Validate and ingest a bundle with attribution from the authenticated identity.

        Args:
            payload: Sample manifest validated by the established ingestion workflow.
            allow_update: Replace an existing bundle through its atomic update workflow.
            increment: Allocate a unique suffixed sample name when creating a new bundle.
            source: Manifest entry route retained in provenance; api or upload.

        Returns:
            Outcome after all sample and dependent writes commit.

        Raises:
            AppError: The current actor lacks internal.ingest:manage.
            ValueError: The existing manifest or file validation fails.
        """

        def ingest(actor: Any, sample: dict[str, Any] | None) -> IngestResult:
            """Authorize the authoritative manifest scope before transactional writes."""
            enforce_sample_ingest_permission(self._runtime, actor, payload)
            return IngestResult.model_validate(
                self._service().ingest_sample_bundle(
                    deepcopy(payload),
                    allow_update=allow_update,
                    increment=increment,
                    ingested_by=actor.username,
                    ingest_source=source,
                )
            )

        return self._runtime.execute(
            "ingest.sample_bundle",
            ("internal.ingest:manage",),
            ingest,
        )

    def authorize_sample(self, payload: dict[str, Any] | None = None) -> None:
        """Check current ingestion grants before staging or inspecting manifest files.

        Args:
            payload: Parsed manifest whose assay and environment are checked; None performs
                the initial sample-edit grant check before reading upload streams.

        Raises:
            AppError: Ingestion, sample-edit or manifest-scope checks fail.
        """
        self._runtime.execute(
            "ingest.authorize_sample",
            ("internal.ingest:manage",),
            lambda actor, sample: enforce_sample_ingest_permission(self._runtime, actor, payload),
        )

    def parse_yaml(self, content: str) -> dict[str, Any]:
        """Parse a YAML manifest with internal.ingest:manage permission.

        Args:
            content: Uploaded or supplied YAML text; no filesystem paths are opened here.

        Returns:
            Validated manifest input accepted by the existing parser.

        Raises:
            AppError: Ingestion permission is denied.
            ValueError: The YAML manifest is invalid.
        """
        return self._runtime.execute(
            "ingest.parse_yaml",
            ("internal.ingest:manage",),
            lambda actor, sample: dict(self._service().parse_yaml_payload(content)),
        )

    def manifest(
        self, *, sample: dict[str, Any] | None, yaml_content: str | None
    ) -> dict[str, Any]:
        """Select and authorize exactly one supplied sample manifest.

        Args:
            sample: Validated manifest object, or None when YAML text is supplied.
            yaml_content: Manifest YAML text, or None when an object is supplied.

        Returns:
            Parsed manifest after current sample-edit and scope authorization.

        Raises:
            AppError: Both inputs, neither input or an unauthorized manifest are supplied.
            ValueError: YAML validation fails.
        """

        def resolve(actor: Any, current: dict[str, Any] | None) -> dict[str, Any]:
            """Check ingestion grants before parsing and scope before any input-file reads."""
            enforce_sample_ingest_permission(self._runtime, actor)
            if not sample and not yaml_content:
                raise api_error(400, "Provide either `sample` or `yaml_content`")
            if sample and yaml_content:
                raise api_error(400, "Provide only one of `sample` or `yaml_content`")
            payload = (
                dict(self._service().parse_yaml_payload(yaml_content))
                if yaml_content
                else deepcopy(sample or {})
            )
            enforce_sample_ingest_permission(self._runtime, actor, payload)
            return payload

        return self._runtime.execute("ingest.manifest", ("internal.ingest:manage",), resolve)

    def authorize_collection(self, collection: str, action: Literal["create", "update"]) -> None:
        """Check collection-specific access before accepting an uploaded document stream.

        Args:
            collection: Requested supported collection name.
            action: create for insertion, or update for replacement.

        Raises:
            AppError: Ingestion or collection-specific access is denied.
        """
        self._runtime.execute(
            "ingest.authorize_collection",
            ("internal.ingest:manage",),
            lambda actor, sample: enforce_collection_permission(
                self._runtime, user=actor, collection=collection, action=action
            ),
        )

    def prepare_upload(
        self,
        *,
        yaml_file: BinaryUpload,
        data_archive: BinaryUpload | None,
        staging_dir: Path,
        allow_update: bool = False,
        increment: bool = False,
    ) -> dict[str, Any]:
        """Resolve uploaded manifests exclusively against their uploaded archive.

        Args:
            yaml_file: Named binary manifest stream; consumed without closing it.
            data_archive: Optional named archive stream; None supplies no attached data.
            staging_dir: Host-created private staging directory.
            allow_update: Permit replacement under the existing duplicate-name policy.
            increment: Allocate a unique sample suffix under the existing name policy.

        Returns:
            Prepared manifest, resolved input paths and any existing ingest warnings.

        Raises:
            AppError: Ingestion or manifest scope is denied.
            ValueError: Invalid archive, unavailable required files or duplicate sample name.
        """

        def prepare(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Authorize before archive extraction and preserve early name conflict checks."""
            from coyote3.application.ingest.upload_bundle import prepare_uploaded_bundle

            enforce_sample_ingest_permission(self._runtime, actor)
            service = self._service()

            def preflight(payload: dict[str, Any]) -> None:
                """Check manifest scope before name lookup or archive extraction."""
                enforce_sample_ingest_permission(self._runtime, actor, payload)
                service.preflight_sample_name(
                    payload, allow_update=allow_update, increment=increment
                )

            return dict(
                prepare_uploaded_bundle(
                    yaml_file=yaml_file,
                    data_archive=data_archive,
                    staging_dir=staging_dir,
                    ingest_service=service,
                    preflight=preflight,
                )
            )

        return self._runtime.execute("ingest.prepare_upload", ("internal.ingest:manage",), prepare)

    def supported_collections(self) -> list[str]:
        """List supported validated collection names with internal.ingest:manage permission."""
        return self._runtime.execute(
            "ingest.supported_collections",
            ("internal.ingest:manage",),
            lambda actor, sample: list(self._service().list_supported_collections()),
        )

    def collection_count(self, collection: str) -> int:
        """Read supported collection occupancy with internal.ingest:manage permission.

        Args:
            collection: Supported collection contract name.

        Returns:
            Number of retained documents in that collection.

        Raises:
            AppError: The current actor lacks ingestion permission.
            ValueError: The collection is unsupported.
        """
        return self._runtime.execute(
            "ingest.collection_count",
            ("internal.ingest:manage",),
            lambda actor, sample: int(self._service().collection_document_count(collection)),
        )

    def _write(self, kind: str, collection: str, values: dict[str, Any]) -> dict[str, Any]:
        """Authorize a supported collection operation and bind its verified submitter."""

        def write(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Apply identity and clinical collection restrictions before writing."""
            enforce_collection_permission(
                self._runtime,
                user=actor,
                collection=collection,
                action="update" if kind == "upsert_document" else "create",
            )
            service = self._service()
            if kind == "insert_document":
                operation = service.insert_collection_document
            elif kind == "insert_documents":
                operation = service.insert_collection_documents
            else:
                operation = service.upsert_collection_document
            return dict(
                operation(collection=collection, **deepcopy(values), ingested_by=actor.username)
            )

        return self._runtime.execute("ingest." + kind, ("internal.ingest:manage",), write)

    def insert_document(
        self, *, collection: str, document: dict[str, Any], ignore_duplicate: bool = True
    ) -> dict[str, Any]:
        """Insert one document after collection-specific authorization.

        Args:
            collection: Supported collection contract name.
            document: Document validated by that collection's authoritative schema.
            ignore_duplicate: Retain an existing identity when True; defaults to True.

        Returns:
            Existing validated insertion outcome.

        Raises:
            AppError: Ingestion or collection-specific access is denied.
            ValueError: Document or collection validation fails.
        """
        return self._write(
            "insert_document",
            collection,
            {"document": document, "ignore_duplicate": ignore_duplicate},
        )

    def insert_documents(
        self, *, collection: str, documents: list[dict[str, Any]], ignore_duplicates: bool = True
    ) -> dict[str, Any]:
        """Insert a batch after collection-specific authorization.

        Args:
            collection: Supported collection contract name.
            documents: Documents validated by the authoritative collection schema.
            ignore_duplicates: Retain existing identities when True; defaults to True.

        Returns:
            Existing validated batch insertion outcome.

        Raises:
            AppError: Ingestion or collection-specific access is denied.
            ValueError: Document or collection validation fails.
        """
        return self._write(
            "insert_documents",
            collection,
            {"documents": documents, "ignore_duplicates": ignore_duplicates},
        )

    def upsert_document(
        self,
        *,
        collection: str,
        match: dict[str, Any],
        document: dict[str, Any],
        upsert: bool = True,
    ) -> dict[str, Any]:
        """Update one supported document after collection-specific authorization.

        Args:
            collection: Supported collection contract name.
            match: Validated ingestion match fields; repository execution remains internal.
            document: Replacement content validated by the collection schema.
            upsert: Create an absent matching identity when True; defaults to True.

        Returns:
            Existing validated update outcome.

        Raises:
            AppError: Ingestion or collection-specific access is denied.
            ValueError: Match, document or collection validation fails.
        """
        return self._write(
            "upsert_document", collection, {"match": match, "document": document, "upsert": upsert}
        )

    def enqueue_sample_bundle(
        self,
        payload: dict[str, Any],
        *,
        allow_update: bool = False,
        increment: bool = False,
        staging_dir: str | None = None,
    ) -> dict[str, Any]:
        """Accept a sample job durably before notifying the worker.

        Args:
            payload: Parsed manifest; current assay and environment access is checked.
            allow_update: Permit the existing atomic replacement workflow.
            increment: Allocate a unique name during worker execution.
            staging_dir: Host-owned durable upload directory, or None for supplied manifests.

        Returns:
            Durable acceptance identifier, task name and configured queue.

        Raises:
            AppError: Ingestion, sample-edit or manifest-scope access is denied.
        """

        def accept(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Preserve manifest scope checks before durable acceptance."""
            enforce_sample_ingest_permission(self._runtime, actor, payload)
            return self._submit(
                actor,
                "sample_bundle",
                payload,
                update_existing=allow_update,
                increment=increment,
                staging_dir=staging_dir,
            )

        return self._runtime.execute(
            "ingest.enqueue_sample_bundle", ("internal.ingest:manage",), accept
        )

    def enqueue_collection(
        self,
        kind: Literal["insert_document", "insert_documents", "upsert_document"],
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Authorize and durably accept a supported validated collection job.

        Args:
            kind: Explicit insertion, batch insertion or update operation.
            payload: The operation's collection, document and supported option fields.

        Returns:
            Durable acceptance identifier, task name and configured queue.

        Raises:
            AppError: Ingestion or collection-specific access is denied.
            ValueError: The operation or asynchronous collection is unsupported.
        """
        if kind not in {"insert_document", "insert_documents", "upsert_document"}:
            raise ValueError("Unsupported durable ingestion job kind")

        def accept(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Validate collection restrictions before recording acceptance."""
            collection = payload["collection"]
            enforce_collection_permission(
                self._runtime,
                user=actor,
                collection=collection,
                action="update" if kind == "upsert_document" else "create",
            )
            self._service().validate_async_collection(collection)
            return self._submit(actor, kind, payload)

        return self._runtime.execute(
            "ingest.enqueue_collection", ("internal.ingest:manage",), accept
        )

    def _submit(
        self, actor: Any, kind: str, payload: dict[str, Any], **options: Any
    ) -> dict[str, Any]:
        """Persist acceptance before broker delivery; retain recovery when the broker fails."""
        identity = submit_ingest_job(
            self._submission.jobs(),
            lambda job_id: self._submission.publish(kind, job_id),
            submitted_by=actor.username,
            kind=kind,
            source_payload=deepcopy(payload),
            **options,
        )
        names = {
            "sample_bundle": "ingest_sample_bundle",
            "insert_document": "insert_collection_document",
            "insert_documents": "insert_collection_documents",
            "upsert_document": "upsert_collection_document",
        }
        return {
            "status": "accepted",
            "task_id": str(identity),
            "task_name": "api.tasks.ingest." + names[kind],
            "queue": self._submission.queue,
        }

    def job_status(self, job_id: str) -> dict[str, Any]:
        """Read a durable job only as its submitter or an authorized superuser.

        Args:
            job_id: Durable acceptance identifier returned by an enqueue operation.

        Returns:
            Public completion state, excluding staged inputs and worker lease tokens.

        Raises:
            AppError: internal.task:view is denied, the job is absent, or another user owns it.
        """

        def read(actor: Any, sample: dict[str, Any] | None) -> dict[str, Any]:
            """Apply ownership checks before shaping public completion data."""
            job = self._submission.jobs().get(job_id)
            if job is None:
                raise api_error(404, "Ingest job not found")
            if not actor.is_superuser and job["submitted_by"] != actor.username:
                raise api_error(403, "This ingest job belongs to another user")
            return dict(job_status_payload(job))

        return self._runtime.execute("ingest.job_status", ("internal.task:view",), read)
