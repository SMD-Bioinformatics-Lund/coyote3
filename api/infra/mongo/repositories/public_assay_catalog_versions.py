"""Transactional persistence for catalog drafts, releases, and revision snapshots."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from bson import ObjectId
from bson.errors import InvalidId

from api.contracts.schemas.public_catalog import PublicAssayCatalogVersionDoc
from api.infra.mongo.repositories.base import BaseRepository
from api.infra.mongo.transactions import run_transaction


class PublicAssayCatalogVersionRepository(BaseRepository):
    """Publish the approved revision and runtime projection in one transaction."""

    def __init__(self, adapter: Any) -> None:
        """Bind governed catalog versions to the runtime Mongo adapter.

        Args:
            adapter: Adapter exposing catalog version, revision, and live collections
                plus the client used for their transactions.
        """
        super().__init__(adapter)
        self.set_collection(adapter.public_assay_catalog_versions_collection)

    def ensure_indexes(self) -> None:
        """Create status/update lookup and unique published content-version indexes."""
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
        """Find a catalog version by document ID.

        Args:
            document_id: Serialized catalog version ObjectId.

        Returns:
            Version document, or ``None`` for an invalid ID or no match.
        """
        try:
            oid = ObjectId(document_id)
        except (InvalidId, TypeError, ValueError):
            return None
        return self.get_collection().find_one({"_id": oid})

    def list(self) -> list[dict[str, Any]]:
        """List version metadata in descending update-time order.

        Returns:
            All version documents with the embedded ``catalog`` field excluded.
        """
        return list(self.get_collection().find({}, {"catalog": 0}).sort("updated_at", -1))

    def revisions(self, document_id: str) -> list[dict[str, Any]]:
        """List stored snapshots for an exact serialized version ID.

        Args:
            document_id: Version identifier matched as a string without ObjectId parsing.

        Returns:
            Snapshot documents in descending revision order.
        """
        return list(
            self.adapter.public_assay_catalog_revisions_collection.find(
                {"version_id": document_id}
            ).sort("revision", -1)
        )

    def _snapshot(self, document: dict[str, Any], session: Any) -> None:
        """Insert a deep-copied version snapshot in the caller's session.

        Args:
            document: Version document with ``_id`` and ``revision``.
            session: Session shared with the owning version write.
        """
        self.adapter.public_assay_catalog_revisions_collection.insert_one(
            {
                "version_id": str(document["_id"]),
                "revision": document["revision"],
                "document": deepcopy(document),
            },
            session=session,
        )

    def insert(self, document: dict[str, Any]) -> dict[str, Any]:
        """Insert a new catalog version and its snapshot in one transaction.

        Args:
            document: Version payload to deep-copy; any supplied ID is replaced.

        Returns:
            Inserted version payload with its newly generated ObjectId.
        """
        payload = deepcopy(document)
        payload["_id"] = ObjectId()

        def transaction(session: Any) -> dict[str, Any]:
            """Persist the captured new version and its revision snapshot together.

            Args:
                session: Transaction session shared by both collections.

            Returns:
                Inserted version payload.
            """
            self.get_collection().insert_one(payload, session=session)
            self._snapshot(payload, session)
            return payload

        return run_transaction(self.adapter.client, transaction)

    def replace(
        self, previous: dict[str, Any], candidate: dict[str, Any], *, publish: bool = False
    ) -> dict[str, Any] | None:
        """Replace an expected version and optionally publish its live projection.

        Args:
            previous: Expected document ID, revision, and status; publication also
                checks its base_version against the current live catalog version.
            candidate: Replacement payload, deep-copied before publication adjustments.
            publish: Also advance the live catalog version and replace its projection;
                defaults to a version-only replacement.

        Returns:
            Stored replacement, or ``None`` for a revision/status mismatch or stale
            publication base version.

        Notes:
            Replacement, snapshot, and optional live publication share a transaction.
            An existing live catalog without a published version record is archived
            with a baseline snapshot before replacement.
        """
        payload = deepcopy(candidate)

        def transaction(session: Any) -> dict[str, Any] | None:
            """Apply the captured replacement and optional release in one session.

            Args:
                session: Session shared by version, live projection, and snapshot writes.

            Returns:
                Replacement payload, or ``None`` if the expected version is stale.

            Notes:
                Publication updates the enclosing payload's catalog and content version.
            """
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

        return run_transaction(self.adapter.client, transaction)


class PublicAssayCatalogRevisionRepository(BaseRepository):
    """Register immutable revision snapshots with managed index inspection."""

    def __init__(self, adapter: Any) -> None:
        """Bind the catalog revision snapshot collection.

        Args:
            adapter: Mongo adapter exposing ``public_assay_catalog_revisions_collection``.
        """
        super().__init__(adapter)
        self.set_collection(adapter.public_assay_catalog_revisions_collection)

    def ensure_indexes(self) -> None:
        """Require each catalog version and revision pair to be unique."""
        self.get_collection().create_index(
            [("version_id", 1), ("revision", 1)], name="catalog_revision_unique", unique=True
        )
