"""MongoDB persistence for center-owned public assay catalog content."""

from __future__ import annotations

from typing import Any

from api.infra.mongo.repositories.base import BaseRepository


class PublicAssayCatalogRepository(BaseRepository):
    """Read the public projection; only governed publication may replace it."""

    def __init__(self, adapter: Any) -> None:
        super().__init__(adapter)
        self.set_collection(self.adapter.public_assay_catalog_collection)

    def ensure_indexes(self) -> None:
        self.get_collection().create_index(
            [("catalog_id", 1)], name="catalog_id_1", unique=True, background=True
        )

    def get_default(self) -> dict[str, Any] | None:
        return self.get_collection().find_one({"catalog_id": "default"})
