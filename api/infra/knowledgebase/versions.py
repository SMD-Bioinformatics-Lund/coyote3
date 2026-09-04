"""Read-only access to installed knowledgebase release metadata."""

from __future__ import annotations

from typing import Any

from api.infra.mongo.repositories.base import BaseRepository


class KnowledgebaseVersionRepository(BaseRepository):
    """Expose sanitized active release manifests from the knowledgebase database."""

    def __init__(self, adapter: Any) -> None:
        super().__init__(adapter)
        self.set_collection(self.adapter.knowledgebase_versions_collection)

    def ensure_indexes(self) -> None:
        """Declare indexes maintained by the knowledgebase importers."""
        self.get_collection().create_index(
            [("source", 1), ("status", 1)], name="source_status", background=True
        )

    def list_active_releases(self) -> list[dict[str, Any]]:
        """Return active versions and aggregate per-release collection counts."""
        projection = {
            "_id": 0,
            "source": 1,
            "release": 1,
            "status": 1,
            "published_at": 1,
            "collections.name": 1,
            "collections.documents": 1,
        }
        rows = self.get_collection().find({"status": "active"}, projection).sort("source", 1)
        releases = []
        for row in rows:
            collections: list[dict[str, Any]] = [
                {
                    "name": str(item.get("name") or ""),
                    "records": int(item.get("documents") or 0),
                }
                for item in row.get("collections") or []
                if isinstance(item, dict) and item.get("name")
            ]
            releases.append(
                {
                    "source": str(row.get("source") or ""),
                    "release": str(row.get("release") or "unknown"),
                    "status": "active",
                    "published_at": row.get("published_at"),
                    "records": sum(item["records"] for item in collections),
                    "collections": collections,
                }
            )
        return releases
