"""MongoDB persistence for governed clinical reporting rule sets."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from bson import BSON, ObjectId
from bson.codec_options import CodecOptions
from bson.errors import InvalidId
from bson.json_util import CANONICAL_JSON_OPTIONS, dumps
from pymongo import ReturnDocument

from api.contracts.schemas.clinical_rules import ClinicalRuleRevisionDoc
from api.infra.mongo.repositories.base import BaseRepository


def _object_id(value: Any) -> ObjectId | None:
    try:
        return value if isinstance(value, ObjectId) else ObjectId(str(value))
    except (InvalidId, TypeError, ValueError):
        return None


def build_revision_snapshot(
    document: dict[str, Any],
    *,
    action: str,
    actor: str,
    occurred_at: datetime,
    reason: str | None,
    previous_revision_hash: str | None,
) -> dict[str, Any]:
    """Build one canonical, hash-chained immutable rule revision."""
    payload = {
        "rule_set_oid": str(document["_id"]),
        "rule_set_id": document["rule_set_id"],
        "content_version": document["content_version"],
        "revision": document["revision"],
        "action": action,
        "actor": actor,
        "occurred_at": occurred_at,
        "reason": reason or None,
        "previous_revision_hash": previous_revision_hash,
        "document": document,
    }
    persisted_payload = BSON.encode(payload).decode(codec_options=CodecOptions(tz_aware=True))
    canonical = dumps(
        persisted_payload,
        json_options=CANONICAL_JSON_OPTIONS,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    persisted_payload["revision_hash"] = hashlib.sha256(canonical).hexdigest()
    return ClinicalRuleRevisionDoc.model_validate(persisted_payload).model_dump(
        mode="python", by_alias=True, exclude_none=True
    )


def verify_revision_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Validate a stored snapshot and verify its canonical digest."""
    parsed = ClinicalRuleRevisionDoc.model_validate(snapshot).model_dump(
        mode="python", by_alias=True, exclude_none=True
    )
    expected = build_revision_snapshot(
        parsed["document"],
        action=parsed["action"],
        actor=parsed["actor"],
        occurred_at=parsed["occurred_at"],
        reason=parsed.get("reason"),
        previous_revision_hash=parsed.get("previous_revision_hash"),
    )
    if expected["revision_hash"] != parsed["revision_hash"]:
        raise RuntimeError("Clinical rule revision integrity verification failed")
    return parsed


class ClinicalRuleRevisionRepository(BaseRepository):
    """Read immutable clinical rule revision snapshots."""

    def __init__(self, adapter: Any) -> None:
        super().__init__(adapter)
        self.set_collection(self.adapter.clinical_rule_revisions_collection)

    def ensure_indexes(self) -> None:
        collection = self.get_collection()
        collection.create_index(
            [("rule_set_oid", 1), ("revision", 1)],
            name="clinical_rule_oid_revision_unique",
            unique=True,
        )
        collection.create_index(
            [("rule_set_id", 1), ("content_version", 1), ("revision", -1)],
            name="clinical_rule_identity_version_revision",
        )
        collection.create_index([("occurred_at", -1)], name="clinical_rule_revision_occurred")

    def list_for_version(self, document_id: Any) -> list[dict[str, Any]]:
        object_id = _object_id(document_id)
        if object_id is None:
            return []
        revisions = list(
            self.get_collection().find({"rule_set_oid": str(object_id)}).sort("revision", -1)
        )
        verified = [verify_revision_snapshot(item) for item in revisions]
        for current, previous in zip(verified, verified[1:], strict=False):
            if current.get("previous_revision_hash") != previous["revision_hash"]:
                raise RuntimeError("Clinical rule revision hash chain is broken")
        return verified

    def get_revision(self, document_id: Any, revision: int) -> dict[str, Any] | None:
        object_id = _object_id(document_id)
        if object_id is None:
            return None
        snapshot = self.get_collection().find_one(
            {"rule_set_oid": str(object_id), "revision": revision}
        )
        return verify_revision_snapshot(snapshot) if snapshot is not None else None


class ClinicalRuleSetRepository(BaseRepository):
    """Store drafts and immutable release history for clinical report rules."""

    def __init__(self, adapter: Any) -> None:
        super().__init__(adapter)
        self.set_collection(self.adapter.clinical_rule_sets_collection)
        self.revision_collection = self.adapter.clinical_rule_revisions_collection

    def _insert_revision(
        self,
        document: dict[str, Any],
        *,
        action: str,
        actor: str,
        reason: str | None,
        occurred_at: datetime,
        session: Any,
        allow_baseline: bool = False,
    ) -> dict[str, Any]:
        previous = self.revision_collection.find_one(
            {"rule_set_oid": str(document["_id"])},
            sort=[("revision", -1)],
            session=session,
        )
        if previous is None and document["revision"] != 1 and not allow_baseline:
            raise RuntimeError(
                "Clinical rule revision baseline is missing; run the revision backfill first"
            )
        if previous is not None and int(previous["revision"]) + 1 != int(document["revision"]):
            raise RuntimeError("Clinical rule revision chain is not contiguous")
        snapshot = build_revision_snapshot(
            document,
            action=action,
            actor=actor,
            occurred_at=occurred_at,
            reason=reason,
            previous_revision_hash=(previous or {}).get("revision_hash"),
        )
        self.revision_collection.insert_one(snapshot, session=session)
        return snapshot

    def ensure_indexes(self) -> None:
        collection = self.get_collection()
        collection.create_index(
            [("rule_set_id", 1), ("content_version", 1)],
            name="rule_set_content_version_unique",
            unique=True,
        )
        collection.create_index(
            [("rule_set_id", 1)],
            name="active_published_rule_set_unique",
            unique=True,
            partialFilterExpression={"active": True, "status": "published"},
        )
        collection.create_index(
            [
                ("scope.asp_id", 1),
                ("scope.subpanel_id", 1),
                ("scope.analyte", 1),
                ("scope.language", 1),
                ("status", 1),
            ],
            name="clinical_rule_scope_status",
        )
        collection.create_index(
            [("status", 1), ("updated_at", -1)], name="clinical_rule_status_updated"
        )
        collection.create_index(
            [("review.clinical_reviewer", 1), ("status", 1)],
            name="clinical_rule_reviewer_status",
        )

    def list_rule_sets(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        query: dict[str, Any] = {}
        if status:
            query["status"] = status
        if search:
            escaped_search = re.escape(search)
            query["$or"] = [
                {"rule_set_id": {"$regex": escaped_search, "$options": "i"}},
                {"name": {"$regex": escaped_search, "$options": "i"}},
                {"scope.asp_id": {"$regex": escaped_search, "$options": "i"}},
                {"scope.subpanel_id": {"$regex": escaped_search, "$options": "i"}},
            ]
        collection = self.get_collection()
        rows = list(
            collection.find(query)
            .sort([("updated_at", -1), ("content_version", -1)])
            .skip(skip)
            .limit(limit)
        )
        return rows, collection.count_documents(query)

    def list_versions(self, rule_set_id: str) -> list[dict[str, Any]]:
        return list(
            self.get_collection()
            .find({"rule_set_id": rule_set_id})
            .sort([("content_version", -1), ("revision", -1)])
        )

    def get(self, document_id: Any) -> dict[str, Any] | None:
        object_id = _object_id(document_id)
        return self.get_collection().find_one({"_id": object_id}) if object_id else None

    def get_active(self, rule_set_id: str) -> dict[str, Any] | None:
        return self.get_collection().find_one(
            {"rule_set_id": rule_set_id, "status": "published", "active": True}
        )

    def list_active_for_assay(self, asp_id: str) -> list[dict[str, Any]]:
        """Return active published rule sets available to one assay."""
        return list(
            self.get_collection()
            .find(
                {
                    "scope.asp_id": asp_id,
                    "status": "published",
                    "active": True,
                }
            )
            .sort([("scope.subpanel_id", 1), ("scope.language", 1)])
        )

    def next_content_version(self, rule_set_id: str) -> int:
        latest = self.get_collection().find_one(
            {"rule_set_id": rule_set_id}, sort=[("content_version", -1)]
        )
        return int((latest or {}).get("content_version") or 0) + 1

    def insert(
        self,
        document: dict[str, Any],
        *,
        action: str,
        actor: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        payload = dict(document)
        payload.setdefault("_id", ObjectId())

        def _transaction(session: Any) -> dict[str, Any]:
            self.get_collection().insert_one(payload, session=session)
            self._insert_revision(
                payload,
                action=action,
                actor=actor,
                reason=reason,
                occurred_at=datetime.now(timezone.utc),
                session=session,
            )
            return payload

        with self.adapter.client.start_session() as session:
            return session.with_transaction(_transaction)

    def update_draft(
        self,
        document_id: Any,
        *,
        expected_revision: int,
        changes: dict[str, Any],
        actor: str,
    ) -> dict[str, Any] | None:
        object_id = _object_id(document_id)
        if object_id is None:
            return None

        def _transaction(session: Any) -> dict[str, Any] | None:
            updated = self.get_collection().find_one_and_update(
                {"_id": object_id, "status": "draft", "revision": expected_revision},
                {"$set": changes, "$inc": {"revision": 1}},
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            if updated is not None:
                self._insert_revision(
                    updated,
                    action="draft_updated",
                    actor=actor,
                    reason=str(changes.get("change_summary") or "") or None,
                    occurred_at=datetime.now(timezone.utc),
                    session=session,
                )
            return updated

        with self.adapter.client.start_session() as session:
            return session.with_transaction(_transaction)

    def delete_draft(self, document_id: Any, *, expected_revision: int) -> dict[str, Any] | None:
        """Delete one editable draft and its private revision snapshots together."""
        object_id = _object_id(document_id)
        if object_id is None:
            return None

        def _transaction(session: Any) -> dict[str, Any] | None:
            deleted = self.get_collection().find_one_and_delete(
                {"_id": object_id, "status": "draft", "revision": expected_revision},
                session=session,
            )
            if deleted is not None:
                self.revision_collection.delete_many(
                    {"rule_set_oid": str(object_id)}, session=session
                )
            return deleted

        with self.adapter.client.start_session() as session:
            return session.with_transaction(_transaction)

    def transition(
        self,
        document_id: Any,
        *,
        from_statuses: set[str],
        changes: dict[str, Any],
        event: dict[str, Any],
    ) -> dict[str, Any] | None:
        object_id = _object_id(document_id)
        if object_id is None:
            return None

        def _transaction(session: Any) -> dict[str, Any] | None:
            updated = self.get_collection().find_one_and_update(
                {"_id": object_id, "status": {"$in": sorted(from_statuses)}},
                {"$set": changes, "$push": {"lifecycle": event}, "$inc": {"revision": 1}},
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            if updated is not None:
                self._insert_revision(
                    updated,
                    action=str(event["action"]),
                    actor=str(event["actor"]),
                    reason=event.get("reason"),
                    occurred_at=event["occurred_at"],
                    session=session,
                )
            return updated

        with self.adapter.client.start_session() as session:
            return session.with_transaction(_transaction)

    def publish(
        self,
        document_id: Any,
        *,
        changes: dict[str, Any],
        event: dict[str, Any],
    ) -> dict[str, Any] | None:
        object_id = _object_id(document_id)
        if object_id is None:
            return None
        result: dict[str, Any] | None = None

        def _transaction(session: Any) -> None:
            nonlocal result
            candidate = self.get_collection().find_one(
                {"_id": object_id, "status": "approved"}, session=session
            )
            if candidate is None:
                return
            previous_versions = list(
                self.get_collection().find(
                    {
                        "rule_set_id": candidate["rule_set_id"],
                        "status": "published",
                        "active": True,
                    },
                    session=session,
                )
            )
            for previous in previous_versions:
                deactivated = self.get_collection().find_one_and_update(
                    {
                        "_id": previous["_id"],
                        "revision": previous["revision"],
                    },
                    {
                        "$set": {
                            "active": False,
                            "updated_at": event["occurred_at"],
                            "updated_by": event["actor"],
                        },
                        "$inc": {"revision": 1},
                    },
                    return_document=ReturnDocument.AFTER,
                    session=session,
                )
                if deactivated is None:
                    raise RuntimeError("Active clinical rule version changed during publication")
                self._insert_revision(
                    deactivated,
                    action="deactivated_by_publish",
                    actor=str(event["actor"]),
                    reason=f"Superseded by content version {candidate['content_version']}",
                    occurred_at=event["occurred_at"],
                    session=session,
                )
            result = self.get_collection().find_one_and_update(
                {"_id": object_id, "status": "approved"},
                {
                    "$set": changes,
                    "$push": {"lifecycle": event},
                    "$inc": {"revision": 1},
                },
                return_document=ReturnDocument.AFTER,
                session=session,
            )
            if result is not None:
                self._insert_revision(
                    result,
                    action=str(event["action"]),
                    actor=str(event["actor"]),
                    reason=event.get("reason"),
                    occurred_at=event["occurred_at"],
                    session=session,
                )

        with self.adapter.client.start_session() as session:
            session.with_transaction(_transaction)
        return result

    def capture_baseline(
        self, document: dict[str, Any], *, actor: str, occurred_at: datetime
    ) -> dict[str, Any] | None:
        """Capture the current state of a pre-snapshot rule document once."""
        if self.revision_collection.find_one({"rule_set_oid": str(document["_id"])}) is not None:
            return None
        return self._insert_revision(
            document,
            action="baseline_captured",
            actor=actor,
            reason="Initial immutable baseline captured from the current rule document",
            occurred_at=occurred_at,
            session=None,
            allow_baseline=True,
        )
