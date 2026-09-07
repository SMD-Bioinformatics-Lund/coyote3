"""Transactional persistence for catalog drafts, releases, and revision snapshots."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from api.contracts.schemas.public_catalog import PublicAssayCatalogVersionDoc
from api.infra.mongo.repositories.base import BaseRepository


class PublicAssayCatalogVersionRepository(BaseRepository):
    """Publish the approved revision and runtime projection in one transaction."""

    def __init__(self, adapter: Any) -> None:
        super().__init__(adapter)
        self.set_collection(adapter.public_assay_catalog_versions_collection)

    def ensure_indexes(self) -> None:
        self.get_collection().create_index(
            [("status", 1), ("updated_at", -1)], name="catalog_status_updated"
        )
        self.get_collection().create_index(
            [("content_version", 1)],
            name="catalog_release_unique",
            unique=True,
            partialFilterExpression={"status": "published"},
        )

    def get(self, document_id: str) -> dict[str, Any] | None:
        try:
            oid = ObjectId(document_id)
        except (InvalidId, TypeError, ValueError):
            return None
        return self.get_collection().find_one({"_id": oid})

    def list(self) -> list[dict[str, Any]]:
        return list(self.get_collection().find({}, {"catalog": 0}).sort("updated_at", -1))

    def revisions(self, document_id: str) -> list[dict[str, Any]]:
        return list(
            self.adapter.public_assay_catalog_revisions_collection.find(
                {"version_id": document_id}
            ).sort("revision", -1)
        )

    def _snapshot(self, document: dict[str, Any], session: Any) -> None:
        self.adapter.public_assay_catalog_revisions_collection.insert_one(
            {
                "version_id": str(document["_id"]),
                "revision": document["revision"],
                "document": deepcopy(document),
            },
            session=session,
        )

    def insert(self, document: dict[str, Any]) -> dict[str, Any]:
        payload = deepcopy(document)
        payload["_id"] = ObjectId()

        def transaction(session: Any) -> dict[str, Any]:
            self.get_collection().insert_one(payload, session=session)
            self._snapshot(payload, session)
            return payload

        with self.adapter.client.start_session() as session:
            return session.with_transaction(transaction)

    def replace(
        self, previous: dict[str, Any], candidate: dict[str, Any], *, publish: bool = False
    ) -> dict[str, Any] | None:
        payload = deepcopy(candidate)

        def transaction(session: Any) -> dict[str, Any] | None:
            if publish:
                live = self.adapter.public_assay_catalog_collection
                current = live.find_one({"catalog_id": "default"}, session=session)
                current_version = int((current or {}).get("version", 0))
                if previous["base_version"] != current_version:
                    return None
                released = deepcopy(payload["catalog"])
                released.pop("_id", None)
                released["version"] = current_version + 1
                released["updated_at"] = payload["updated_at"]
                released["updated_by"] = payload["published_by"]
                payload["catalog"] = released
                payload["content_version"] = released["version"]
            result = self.get_collection().replace_one(
                {
                    "_id": previous["_id"],
                    "revision": previous["revision"],
                    "status": previous["status"],
                },
                payload,
                session=session,
            )
            if not result.matched_count:
                return None
            if publish:
                # Preserve the baseline when upgrading an existing live catalog.
                if current and not self.get_collection().find_one(
                    {"status": "published", "content_version": current_version}, session=session
                ):
                    baseline = PublicAssayCatalogVersionDoc(
                        _id=ObjectId(),
                        catalog=current,
                        content_version=current_version,
                        base_version=max(0, current_version - 1),
                        revision=1,
                        status="published",
                        created_at=current["created_at"],
                        created_by=current["created_by"],
                        updated_at=current["updated_at"],
                        updated_by=current["updated_by"],
                        lifecycle=[
                            {
                                "action": "baseline_archived",
                                "actor": payload["published_by"],
                                "occurred_at": payload["updated_at"],
                            }
                        ],
                    ).model_dump(by_alias=True)
                    self.get_collection().insert_one(baseline, session=session)
                    self._snapshot(baseline, session)
                live.replace_one({"catalog_id": "default"}, released, upsert=True, session=session)
            self._snapshot(payload, session)
            return payload

        with self.adapter.client.start_session() as session:
            return session.with_transaction(transaction)


class PublicAssayCatalogRevisionRepository(BaseRepository):
    """Register immutable revision snapshots with managed index inspection."""

    def __init__(self, adapter: Any) -> None:
        super().__init__(adapter)
        self.set_collection(adapter.public_assay_catalog_revisions_collection)

    def ensure_indexes(self) -> None:
        self.get_collection().create_index(
            [("version_id", 1), ("revision", 1)], name="catalog_revision_unique", unique=True
        )
