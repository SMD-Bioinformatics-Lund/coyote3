"""Repository for sample-scoped pharmacogenomic results."""

from api.contracts.operations import OperationResult
from api.infra.mongo.repositories.base import BaseRepository


class PgxRepository(BaseRepository):
    """Read and manage PGX results linked to an ingested sample."""

    def __init__(self, adapter):
        """Bind the sample-scoped pharmacogenomic result collection.

        Args:
            adapter: Mongo adapter exposing ``pgx_collection``.
        """
        super().__init__(adapter)
        self.set_collection(self.adapter.pgx_collection)

    def ensure_indexes(self) -> None:
        """Create the sample identifier lookup index for PGX results."""
        self.get_collection().create_index([("SAMPLE_ID", 1)], name="sample_id_1", background=True)

    def get_sample_pgx(self, sample_id: str) -> list[dict]:
        """Read PGX results for an exact sample identifier.

        Args:
            sample_id: Stored ``SAMPLE_ID`` string; no ObjectId conversion is applied.

        Returns:
            Matching documents with no explicit sort, or an empty list.
        """
        return list(self.get_collection().find({"SAMPLE_ID": sample_id}))

    def delete_sample_pgx(self, sample_id: str) -> OperationResult:
        """Delete a sample's PGX results in one transaction.

        Args:
            sample_id: Exact stored ``SAMPLE_ID`` string.

        Returns:
            Deletion counts expressed as an application operation result.
        """
        return OperationResult.from_delete(self.delete_many_atomic({"SAMPLE_ID": sample_id}))
