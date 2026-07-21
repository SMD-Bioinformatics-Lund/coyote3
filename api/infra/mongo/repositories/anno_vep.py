"""Immutable VEP transcript annotation vault repository."""

from __future__ import annotations

from typing import Any

from pymongo import UpdateOne

from api.infra.mongo.repositories.base import BaseRepository


class AnnoVepRepository(BaseRepository):
    """Store all VEP transcript consequences keyed by variant identity and VEP version."""

    def __init__(self, adapter):
        super().__init__(adapter)
        self.set_collection(self.adapter.anno_vep_collection)

    def ensure_indexes(self) -> None:
        """Create lookup indexes for transcript backfilling."""
        col = self.get_collection()
        col.create_index(
            [("simple_id_hash", 1), ("vep_version", 1)],
            name="simple_id_hash_1_vep_version_1",
            unique=True,
            background=True,
        )
        col.create_index(
            [("CSQ.Feature", 1), ("vep_version", 1)],
            name="csq_feature_1_vep_version_1",
            background=True,
        )

    def upsert_many(self, docs: list[dict[str, Any]], *, session: Any | None = None) -> int:
        """Upsert transcript vault documents without mutating existing identity keys."""
        if not docs:
            return 0
        operations: list[UpdateOne] = []
        for doc in docs:
            simple_id_hash = str(doc.get("simple_id_hash") or "").strip()
            vep_version = str(doc.get("vep_version") or "").strip()
            if not simple_id_hash or not vep_version:
                continue
            operations.append(
                UpdateOne(
                    {"simple_id_hash": simple_id_hash, "vep_version": vep_version},
                    {"$set": dict(doc)},
                    upsert=True,
                )
            )
        if not operations:
            return 0
        kwargs = {"session": session} if session is not None else {}
        result = self.get_collection().bulk_write(operations, ordered=False, **kwargs)
        return int((result.upserted_count or 0) + (result.modified_count or 0))

    def get_for_variant(self, *, simple_id_hash: str, vep_version: str) -> dict[str, Any] | None:
        """Return a transcript vault document for a variant/version pair."""
        return self.get_collection().find_one(
            {"simple_id_hash": str(simple_id_hash), "vep_version": str(vep_version)}
        )
