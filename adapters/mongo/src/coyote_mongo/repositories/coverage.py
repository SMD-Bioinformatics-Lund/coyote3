# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Sample-owned interval coverage, separate from D4 gene/exon summaries."""

from typing import Any

from coyote_mongo.repositories.base import BaseRepository


class CoverageRepository(BaseRepository):
    """Bind interval reads to the sample identifier used by transactional ingestion."""

    def __init__(self, adapter: Any) -> None:
        """Bind the configured primary collection without writing to it."""
        super().__init__(adapter)
        self.set_collection(adapter.coverage_collection)

    def ensure_indexes(self) -> None:
        """Index sample lookup/deletion and deterministic interval ordering."""
        self.get_collection().create_index(
            [("SAMPLE_ID", 1), ("chr", 1), ("start", 1), ("end", 1)],
            name="sample_interval",
            background=True,
        )

    def get_sample_intervals(self, sample_id: str) -> list[dict[str, Any]]:
        """Read intervals by serialized sample ObjectId; absent samples yield no rows."""
        return list(
            self.get_collection()
            .find({"SAMPLE_ID": sample_id})
            .sort([("chr", 1), ("start", 1), ("end", 1), ("_id", 1)])
        )
