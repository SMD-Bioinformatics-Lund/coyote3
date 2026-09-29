#!/usr/bin/env python3
"""Repair verified draft snapshot null-stripping failures; never accept unknown digests."""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

from bson import BSON
from bson.json_util import CANONICAL_JSON_OPTIONS, dumps
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.infra.mongo.repositories.clinical_rule_sets import (  # noqa: E402
    build_revision_snapshot,
    verify_revision_snapshot,
)
from api.infra.mongo.transactions import run_transaction  # noqa: E402


def verify_affected_snapshot(snapshot: dict) -> None:
    """Prove a failed digest by restoring the single null lost by draft serialization.

    Args:
        snapshot: Original stored revision, including its unmodified digest.

    Raises:
        ValueError: Revision is not the known draft failure or its digest cannot be reproduced.
    """
    document = snapshot["document"]
    if (
        snapshot["action"] != "draft_updated"
        or document["status"] != "draft"
        or "content_hash" in document
    ):
        raise ValueError("Revision does not match the supported null-stripping repair")
    payload = {
        key: snapshot[key]
        for key in (
            "rule_set_oid",
            "rule_set_id",
            "content_version",
            "revision",
            "action",
            "actor",
            "occurred_at",
        )
    }
    payload.update(
        document=dict(document, content_hash=None),
        reason=snapshot.get("reason"),
        previous_revision_hash=snapshot.get("previous_revision_hash"),
    )
    digest = hashlib.sha256(
        dumps(
            payload,
            json_options=CANONICAL_JSON_OPTIONS,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    if digest != snapshot["revision_hash"]:
        raise ValueError("Original revision digest cannot be reproduced; no repair is permitted")


def repair(db, *, backup_file: Path | None = None, apply: bool = False) -> dict[str, int]:
    """Verify original chains and transactionally replace only affected snapshots.

    Args:
        db: Explicit development application database.
        backup_file: New BSON backup file required for writes; created with mode 0600.
        apply: False inspects only. True backs up originals and applies the reviewed plan.

    Returns:
        Counts of proven serialization failures and changed revision snapshots.

    Raises:
        ValueError: Unknown corruption, broken chains, report references, missing backup
            path or a concurrent modification prevents a safe repair.
        FileExistsError: The backup already exists; it is never overwritten.

    Notes:
        Pause rule writers before applying. The backup contains complete original
        revisions and must be protected as application data. Samples and reports
        are never modified. The runtime verifier has no compatibility fallback.
    """
    mapping = load_collection_section("primary")
    revisions = db[mapping["clinical_rule_revisions_collection"]]
    old_hashes, new_hashes = {}, {}
    changes = []
    failures = 0
    for source in revisions.find({}).sort([("rule_set_oid", 1), ("revision", 1)]):
        try:
            verify_revision_snapshot(source)
        except RuntimeError:
            verify_affected_snapshot(source)
            failures += 1
        identity = source["rule_set_oid"]
        if source.get("previous_revision_hash") != old_hashes.get(identity):
            raise ValueError("Original revision chain is broken")
        old_hashes[identity] = source["revision_hash"]
        updated = build_revision_snapshot(
            source["document"],
            action=source["action"],
            actor=source["actor"],
            occurred_at=source["occurred_at"],
            reason=source.get("reason"),
            previous_revision_hash=new_hashes.get(identity),
        )
        verify_revision_snapshot(updated)
        new_hashes[identity] = updated["revision_hash"]
        if updated["revision_hash"] != source["revision_hash"]:
            changes.append((source, dict(updated, _id=source["_id"])))
    affected = sorted({source["rule_set_oid"] for source, _ in changes})
    if affected and db[mapping["reports_collection"]].find_one(
        {
            "clinical_rule_source.source.rule_set_oid": {"$in": affected},
        }
    ):
        raise ValueError(
            "Saved report references an affected rule version; automatic repair refused"
        )
    if apply and changes:
        if backup_file is None:
            raise ValueError("An exclusive backup file is required before repair")
        fd = os.open(backup_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as backup:
            for source, _ in changes:
                backup.write(BSON.encode(source))
            backup.flush()
            os.fsync(backup.fileno())

        def write(session):
            """Use original documents as optimistic transaction preconditions."""
            for source, updated in changes:
                result = revisions.replace_one(source, updated, session=session)
                if result.matched_count != 1:
                    raise ValueError("A revision changed after preflight; repair aborted")

        run_transaction(db.client, write)
    return {"verified_serialization_failures": failures, "revisions_to_replace": len(changes)}


def main() -> int:
    """Run the explicit-target dry run, or backed-up repair when --apply is supplied."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup-file", type=Path)
    args = parser.parse_args()
    uri, name = os.getenv("COYOTE3_MONGO_URI"), os.getenv("COYOTE3_DB")
    if not uri or not name:
        parser.error("Set COYOTE3_MONGO_URI and COYOTE3_DB explicitly")
    if args.apply and not args.backup_file:
        parser.error("--apply requires --backup-file")
    with MongoClient(uri, serverSelectionTimeoutMS=7000) as client:
        print(repair(client[name], apply=args.apply, backup_file=args.backup_file))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
