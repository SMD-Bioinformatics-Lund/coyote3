"""Repository for sample-scoped pharmacogenomic results."""

from api.contracts.operations import OperationResult
from api.infra.mongo.repositories.base import BaseRepository


class PgxRepository(BaseRepository):
    """Read and manage PGX results linked to an ingested sample."""

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.pgx_collection)

    def ensure_indexes(self) -> None:
        self.get_collection().create_index([("SAMPLE_ID", 1)], name="sample_id_1", background=True)

    def get_sample_pgx(self, sample_id: str) -> list[dict]:
        return list(self.get_collection().find({"SAMPLE_ID": sample_id}))

    def delete_sample_pgx(self, sample_id: str) -> OperationResult:
        return OperationResult.from_delete(
            self.get_collection().delete_many({"SAMPLE_ID": sample_id})
        )
