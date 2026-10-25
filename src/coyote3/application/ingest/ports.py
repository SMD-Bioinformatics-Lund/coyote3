"""Storage and transaction operations required by ingestion workflows."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, TypeVar

from coyote3.domain.persistence import ReplaceDocumentResult
from coyote3.domain.selection import Selection

ResultT = TypeVar("ResultT")


class IngestGateway(Protocol):
    """Persist ingestion data without exposing database clients or collections."""

    def collection_names(self) -> set[str]:
        """Return the collections actually configured for this ingest gateway."""
        ...

    def find_document(
        self, name: str, selector: dict[str, Any], *, session: Any = None
    ) -> dict[str, Any] | None:
        """Read a configured ingest document on its owning client's transaction.

        Args:
            name: Registered logical ingest collection name.
            selector: Exact MongoDB predicate prepared by the workflow.
            session: Session from the destination client; None reads outside a transaction.

        Returns:
            The matching document, or None when it does not exist.

        Raises:
            ValueError: The logical collection is not configured for ingestion.
        """
        ...

    def hgnc_documents(self, projection: dict[str, int]) -> list[dict[str, Any]]:
        """Read reference gene metadata used to normalize transcript annotations.

        Args:
            projection: HGNC fields required for symbol/transcript resolution.

        Returns:
            Projected reference documents from the configured knowledgebase collection.
        """
        ...

    def sample_names(self, selector: Selection) -> list[dict[str, Any]]:
        """Read existing sample names for collision detection before ingest.

        Args:
            selector: Exact-name or escaped-name-pattern predicate.

        Returns:
            Matching sample identifiers and names without other clinical metadata.
        """
        ...

    def insert_dependent(self, name: str, document: dict[str, Any], *, session: Any) -> None:
        """Insert one validated measurement in the active bundle transaction.

        Args:
            name: Registered destination for the measurement.
            document: Validated measurement with canonical sample ownership.
            session: Owning bundle session; None is reserved for direct test/import callers.
        """
        ...

    def insert_dependents(
        self, name: str, documents: list[dict[str, Any]], *, session: Any
    ) -> None:
        """Insert validated finding rows without starting another transaction.

        Args:
            name: Registered destination for the finding type.
            documents: Validated rows containing canonical sample ownership.
            session: Active bundle session passed through to the bulk writer.
        """
        ...

    def delete_dependents(self, name: str, sample_id: str, *, session: Any) -> None:
        """Remove evidence owned by one sample before transactional replacement.

        Args:
            name: Registered destination for the evidence type.
            sample_id: Canonical serialized sample identifier matched against SAMPLE_ID.
            session: Active bundle session containing replacement writes.
        """
        ...

    def document_count(self, name: str) -> int:
        """Return estimated occupancy without scanning all ingest records.

        Args:
            name: Registered logical ingest collection name.

        Returns:
            Estimated document count; zero for an empty collection.
        """
        ...

    def create_sample(self, document: dict[str, Any], *, session: Any) -> None:
        """Insert validated sample metadata inside the bundle transaction.

        Args:
            document: Current-schema sample anchor with its preallocated provider ID.
            session: Application-database transaction shared with dependent writes.
        """
        ...

    def set_sample_fields(
        self, selector: dict[str, Any], fields: dict[str, Any], *, session: Any
    ) -> None:
        """Set prepared sample state fields inside the owning bundle transaction.

        Args:
            selector: Sample identity predicate already checked by the workflow.
            fields: Validated metadata/state values to set; no upsert is performed.
            session: Owning application-database transaction.
        """
        ...

    def replace_document(
        self,
        name: str,
        selector: dict[str, Any],
        document: dict[str, Any],
        *,
        upsert: bool,
        session: Any,
    ) -> ReplaceDocumentResult:
        """Replace a validated ingest document and return portable write counts.

        Args:
            name: Registered logical ingest collection name.
            selector: Nonempty identity predicate validated by the application.
            document: Complete validated replacement, including preserved provenance.
            upsert: Permit insertion when the selector has no match.
            session: Destination-client transaction, never a different database client's session.

        Returns:
            Matched/modified counts and the serialized inserted ID when upserted.
        """
        ...

    def sample_biomarkers(self, sample_id: str, *, session: Any) -> list[dict[str, Any]]:
        """Read measurements in the same transaction that will replace supplied analyses.

        Args:
            sample_id: Parent sample's string identifier.
            session: Active ingest transaction from this gateway's application client.

        Returns:
            Existing measurement documents, including their source identity.
        """
        ...

    def run_transaction(self, operation: Callable[[Any], ResultT]) -> ResultT:
        """Commit all bundle writes together or propagate the transaction failure."""
        ...

    def validate_completion_target(self, name: str) -> None:
        """Reject remote writes that cannot share the app's ingest receipt transaction."""
        ...

    def run_collection_transaction(self, name: str, operation: Callable[[Any], ResultT]) -> ResultT:
        """Run a transaction on the client owning a named ingest collection.

        Args:
            name: Configured ingest collection name.
            operation: Callback receiving the transaction's session.

        Returns:
            The callback's result after successful transaction completion.

        Raises:
            ValueError: If the collection name is not configured.

        Notes:
            Transaction failures propagate from the shared transaction runner.
        """
        ...

    def insert_documents(
        self,
        name: str,
        documents: list[dict[str, Any]],
        *,
        ignore_duplicates: bool = False,
        record_completion: Callable[..., Any] | None = None,
    ) -> dict[str, Any]:
        """Insert a batch atomically, retrying without explicitly ignored duplicates.

        Duplicate errors abort a MongoDB transaction. Filter only the reported duplicate
        rows after abort, then retry the entire remaining batch, never a partial commit.
        """
        ...

    def new_sample_id(self) -> str:
        """Allocate a serialized sample identifier."""
        ...

    def provider_sample_id(self, value: str) -> Any:
        """Resolve a serialized identifier for the storage provider."""
        ...
