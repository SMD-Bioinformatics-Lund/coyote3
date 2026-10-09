"""Canonical hash-linked snapshots for query-rule governance."""

import hashlib
from typing import Any

from bson import BSON
from bson.codec_options import CodecOptions
from bson.json_util import CANONICAL_JSON_OPTIONS, dumps

from api.contracts.schemas.query_rules import QueryRuleDoc, QueryRuleRevisionDoc
from api.infra.mongo.repositories.base import BaseRepository


def build_query_revision(document: dict, action: str, previous_hash: str | None = None) -> dict:
    """Build a BSON-stable snapshot of the exact stored version.

    Args:
        document: Complete rule version with database identity and revision.
        action: Audited lifecycle action or explicit migration baseline.
        previous_hash: Digest of the preceding revision, or None for a baseline.

    Returns:
        Validated immutable snapshot with a canonical SHA-256 digest.
    """
    doc = QueryRuleDoc.model_validate(document).model_dump(by_alias=True, exclude_none=True)
    payload = {
        "rule_oid": str(doc["_id"]),
        "scope_key": doc["scope_key"],
        "version": doc["version"],
        "revision": doc["revision"],
        "action": action,
        "actor": doc["updated_by"],
        "occurred_at": doc["updated_on"],
        "previous_revision_hash": previous_hash,
        "document": doc,
    }
    payload = BSON.encode(payload).decode(codec_options=CodecOptions(tz_aware=True))
    payload["revision_hash"] = hashlib.sha256(
        dumps(
            payload, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    return QueryRuleRevisionDoc.model_validate(payload).model_dump(by_alias=True, exclude_none=True)


class QueryRuleRevisionRepository(BaseRepository):
    """Read immutable query-rule snapshots and verify their integrity."""

    def __init__(self, adapter: Any) -> None:
        """Bind the configured revision collection.

        Args:
            adapter: Application adapter exposing query_rule_revisions_collection.
        """
        super().__init__(adapter)
        self.set_collection(adapter.query_rule_revisions_collection)

    def ensure_indexes(self) -> None:
        """Enforce one immutable snapshot per document revision."""
        self.get_collection().create_index(
            [("rule_oid", 1), ("revision", 1)], unique=True, name="query_rule_revision_unique"
        )

    def list_for_version(self, identifier: str) -> list[dict]:
        """Return verified snapshots in newest-first order.

        Args:
            identifier: Serialized rule version ObjectId.

        Returns:
            Verified revision history, empty for an unknown version.

        Raises:
            RuntimeError: Snapshot content or hash-chain continuity is invalid.
        """
        rows = list(self.get_collection().find({"rule_oid": identifier}).sort("revision", -1))
        for row in rows:
            row = BSON.encode(row).decode(codec_options=CodecOptions(tz_aware=True))
            expected = build_query_revision(
                row["document"], row["action"], row.get("previous_revision_hash")
            )
            if any(row.get(key) != expected.get(key) for key in expected if key != "_id"):
                # BSON dates can differ in timezone representation but compare by instant.
                raise RuntimeError("Query rule revision integrity verification failed")
        for current, previous in zip(rows, rows[1:]):
            if current.get("previous_revision_hash") != previous["revision_hash"]:
                raise RuntimeError("Query rule revision chain is broken")
        return rows
