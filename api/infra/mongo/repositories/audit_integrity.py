"""Atomic, idempotent traceability audit chains and snapshot verification."""

from hashlib import sha256
from typing import Any

from bson import BSON, json_util
from bson.codec_options import CodecOptions
from pymongo.errors import DuplicateKeyError, PyMongoError

from api.config.operational_collections import OPERATIONAL_COLLECTIONS
from api.infra.mongo.transactions import run_transaction

GENESIS_HASH = "0" * 64


def event_hash(document: dict[str, Any]) -> str:
    """Hash canonical BSON content including chain position and previous hash.

    MongoDB stores datetimes at millisecond precision. A BSON round trip ensures
    the hash is identical before insertion and after reading the persisted event.
    Only the derived entry hash itself is excluded.
    """
    payload = {**document, "integrity": dict(document["integrity"])}
    payload["integrity"].pop("entry_hash", None)
    normalized = BSON.encode(payload).decode(codec_options=CodecOptions(tz_aware=True))
    canonical = json_util.dumps(
        normalized,
        json_options=json_util.CANONICAL_JSON_OPTIONS,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(canonical.encode("utf-8")).hexdigest()


def append_event(collection: Any, document: dict[str, Any]) -> Any:
    """Insert once, chaining non-expiring clinical events in an owning transaction.

    Args:
        collection: Destination audit collection on the identity MongoDB client.
        document: Redacted event with a stable _id. Existing IDs are never rewritten.

    Returns:
        The persisted event identifier, including on duplicate delivery.

    Raises:
        PyMongoError: Persistence, transaction support, or concurrent initialization fails.

    Notes:
        Heads are serialized by MongoDB transaction write conflicts. Each environment
        has a separate chain. Expiring operational events are deliberately not chained.
    """
    if document.get("retention_class") != "traceability":
        try:
            result = collection.insert_one(document)
        except DuplicateKeyError:
            # Stable event identities make replay safe without granting update access.
            return document["_id"]
        if not result.acknowledged:
            raise PyMongoError("Audit inserts require acknowledged write concern")
        return document["_id"]
    environment = str((document.get("source") or {}).get("environment") or "unknown")
    chain_id = sha256(f"{collection.name}:{environment}".encode()).hexdigest()
    heads = collection.database[OPERATIONAL_COLLECTIONS.audit_chain_heads]

    def append(session: Any) -> Any:
        """Commit an event and its chain head together, or preserve the existing event."""
        if collection.find_one({"_id": document["_id"]}, {"_id": 1}, session=session):
            return document["_id"]
        previous = heads.find_one({"_id": chain_id}, session=session) or {}
        integrity = {
            "version": 1,
            "chain_id": chain_id,
            "sequence": int(previous.get("sequence", 0)) + 1,
            "previous_hash": previous.get("entry_hash", GENESIS_HASH),
        }
        event = {**document, "immutable": True, "integrity": integrity}
        event.pop("expires_at", None)
        integrity["entry_hash"] = event_hash(event)
        collection.insert_one(event, session=session)
        heads.replace_one(
            {"_id": chain_id},
            {
                "_id": chain_id,
                "collection": collection.name,
                "environment": environment,
                "event_id": document["_id"],
                **integrity,
            },
            upsert=True,
            session=session,
        )
        return document["_id"]

    # Concurrent first events can collide on the head's _id before MongoDB can
    # label the transaction as a transient write conflict. Retry that race only.
    for attempt in range(5):
        try:
            return run_transaction(collection.database.client, append)
        except DuplicateKeyError:
            if attempt == 4:
                raise
    raise PyMongoError("Audit chain initialization failed")


def verify_chain(collection: Any, *, checkpoint: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify all traceability chains in a consistent database snapshot.

    Args:
        collection: Identity audit collection to verify, without modifying it.
        checkpoint: Previously exported verifier result from independent storage.

    Returns:
        Status, error descriptions, legacy event count, and current chain checkpoints.
        A valid result verifies chained events only, never unchained historical events.

    Notes:
        SHA-256 chains detect alteration, removal and reordering relative to trusted
        heads. An independently retained checkpoint is required to detect an attacker
        who rewrites both events and heads or truncates the entire chain.
    """
    if checkpoint is not None:
        rows = checkpoint.get("chains")
        if (
            checkpoint.get("valid") is not True
            or not isinstance(rows, list)
            or any(
                not isinstance(row, dict)
                or not isinstance(row.get("chain_id"), str)
                or type(row.get("sequence")) is not int
                or row["sequence"] < 1
                or not isinstance(row.get("entry_hash"), str)
                or len(row["entry_hash"]) != 64
                for row in rows
            )
        ):
            raise ValueError("Checkpoint must be a successful audit verification result")
        if len({row["chain_id"] for row in rows}) != len(rows):
            raise ValueError("Checkpoint contains duplicate chains")

    def verify(session: Any) -> dict[str, Any]:
        """Read heads and events at one snapshot without racing concurrent appends."""
        heads = list(
            collection.database[OPERATIONAL_COLLECTIONS.audit_chain_heads].find(
                {"collection": collection.name}, session=session
            )
        )
        expected = {row["chain_id"]: row for row in (checkpoint or {}).get("chains", [])}
        errors: list[str] = []
        chains: list[dict[str, Any]] = []
        for head in heads:
            chain_id = head["_id"]
            sequence, previous, last_id = 0, GENESIS_HASH, None
            anchor = expected.pop(chain_id, None)
            anchor_seen = anchor is None
            cursor = collection.find({"integrity.chain_id": chain_id}, session=session).sort(
                "integrity.sequence", 1
            )
            for event in cursor:
                proof = event.get("integrity", {})
                sequence += 1
                if (
                    proof.get("version") != 1
                    or proof.get("sequence") != sequence
                    or proof.get("previous_hash") != previous
                    or proof.get("entry_hash") != event_hash(event)
                ):
                    errors.append(f"Chain {chain_id}: invalid event at position {sequence}")
                if event.get("retention_class") != "traceability" or "expires_at" in event:
                    errors.append(f"Chain {chain_id}: expiring or non-clinical event")
                if anchor and proof.get("sequence") == anchor.get("sequence"):
                    anchor_seen = proof.get("entry_hash") == anchor.get("entry_hash")
                previous, last_id = proof.get("entry_hash"), event["_id"]
            if (
                sequence != head.get("sequence")
                or previous != head.get("entry_hash")
                or last_id != head.get("event_id")
            ):
                errors.append(f"Chain {chain_id}: head does not match its events")
            if not anchor_seen:
                errors.append(f"Chain {chain_id}: trusted checkpoint is missing or changed")
            chains.append({"chain_id": chain_id, "sequence": sequence, "entry_hash": previous})
        if expected:
            errors.append("Trusted checkpoint contains chains missing from the database")
        known = [row["chain_id"] for row in chains]
        if collection.count_documents(
            {"integrity": {"$exists": True}, "integrity.chain_id": {"$nin": known}}, session=session
        ):
            errors.append("Chained events exist without an owning head")
        legacy = collection.count_documents(
            {"retention_class": "traceability", "integrity": {"$exists": False}}, session=session
        )
        return {
            "valid": not errors,
            "errors": errors,
            "unchained_legacy_events": legacy,
            "chains": chains,
        }

    return run_transaction(collection.database.client, verify)
