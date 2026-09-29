#!/usr/bin/env python3
"""Remove the unreleased engine counter from development rule records and hashes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from copy import deepcopy
from pathlib import Path

from bson import BSON
from bson.codec_options import CodecOptions
from bson.json_util import CANONICAL_JSON_OPTIONS, dumps
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.application.reporting.clinical_rules.validation import (  # noqa: E402
    canonical_content,
    content_hash,
)
from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc  # noqa: E402
from api.infra.mongo.repositories.clinical_rule_sets import (  # noqa: E402
    build_revision_snapshot,
    verify_revision_snapshot,
)
from api.infra.mongo.transactions import run_transaction  # noqa: E402


def clean_rule(source: dict) -> dict:
    """Remove the obsolete field after verifying any stored content digest.

    Args:
        source: Stored development rule document, possibly using the old counter.

    Returns:
        Independent document with a recalculated digest when one was present.

    Raises:
        ValueError: The original content digest does not match its definition.
    """
    result = deepcopy(source)
    if "minimum_engine_version" not in result:
        return result
    version = result.pop("minimum_engine_version")
    parsed = ClinicalRuleSetDoc.model_validate(result)
    if source.get("content_hash"):
        old_content = canonical_content(parsed)
        old_content["minimum_engine_version"] = version
        digest = hashlib.sha256(
            json.dumps(
                old_content, sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        if digest != source["content_hash"]:
            raise ValueError("Rule content integrity check failed; no records were written")
        result["content_hash"] = content_hash(parsed)
    return result


def verify_original_snapshot(source: dict) -> None:
    """Verify the old snapshot format before rebuilding its development-only chain.

    Args:
        source: Stored snapshot, with or without the obsolete engine counter.

    Raises:
        ValueError: Snapshot content or digest fails integrity verification.
    """
    if "minimum_engine_version" not in source["document"]:
        verify_revision_snapshot(source)
        return
    document = deepcopy(source["document"])
    version = document.pop("minimum_engine_version")
    document = ClinicalRuleSetDoc.model_validate(document).model_dump(
        mode="python", by_alias=True, exclude_none=True
    )
    document["minimum_engine_version"] = version
    payload = {
        key: source[key]
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
        document=document,
        reason=source.get("reason") or None,
        previous_revision_hash=source.get("previous_revision_hash"),
    )
    persisted = BSON.encode(payload).decode(codec_options=CodecOptions(tz_aware=True))
    digest = hashlib.sha256(
        dumps(
            persisted, json_options=CANONICAL_JSON_OPTIONS, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    if digest != source["revision_hash"]:
        raise ValueError("Rule revision integrity check failed; no records were written")


def migrate(db, *, apply: bool = False) -> dict[str, int]:
    """Plan or atomically apply the development-only rule contract cleanup.

    Args:
        db: Explicit application database containing the development rules.
        apply: Persist the plan only when True; otherwise inspect without writing.

    Returns:
        Counts of changed rule documents and revision snapshots.

    Raises:
        ValueError: Reports exist, integrity checks fail, or a document changes
            between preflight and the transaction.

    Notes:
        Stop all application writers and take a backup first. Any saved report
        blocks this migration; issued-report provenance must never be rewritten.
        This script does not update samples or rule content version numbers.
    """
    mapping = load_collection_section("primary")
    rules = db[mapping["clinical_rule_sets_collection"]]
    revisions = db[mapping["clinical_rule_revisions_collection"]]
    reports = db[mapping["reports_collection"]]
    changes = []
    counts = {"rules": 0, "revisions": 0}
    for source in rules.find({"minimum_engine_version": {"$exists": True}}):
        changes.append((rules, source, clean_rule(source)))
        counts["rules"] += 1
    old_hashes: dict[str, str] = {}
    new_hashes: dict[str, str] = {}
    for source in revisions.find({}).sort([("rule_set_oid", 1), ("revision", 1)]):
        verify_original_snapshot(source)
        identity = source["rule_set_oid"]
        if source.get("previous_revision_hash") != old_hashes.get(identity):
            raise ValueError("Rule revision chain is broken; no records were written")
        old_hashes[identity] = source["revision_hash"]
        updated = build_revision_snapshot(
            clean_rule(source["document"]),
            action=source["action"],
            actor=source["actor"],
            occurred_at=source["occurred_at"],
            reason=source.get("reason"),
            previous_revision_hash=new_hashes.get(identity),
        )
        new_hashes[identity] = updated["revision_hash"]
        if updated["revision_hash"] != source["revision_hash"]:
            changes.append((revisions, source, dict(updated, _id=source["_id"])))
            counts["revisions"] += 1
    if changes and reports.find_one({}):
        raise ValueError(
            "Saved reports exist; this cleanup is only for unreleased development data"
        )
    if apply and changes:

        def write(session):
            """Recheck report protection and replace only unchanged planned documents."""
            if reports.find_one({}, session=session):
                raise ValueError("Saved reports exist; migration refused")
            for collection, original, updated in changes:
                if collection.replace_one(original, updated, session=session).matched_count != 1:
                    raise ValueError("Rule history changed; stop writers and rerun the plan")

        run_transaction(db.client, write)
    return counts


def main() -> int:
    """Run a read-only plan unless --apply explicitly authorizes development writes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=os.environ.get("COYOTE3_MONGO_URI"))
    parser.add_argument("--db", default=os.environ.get("COYOTE3_DB"))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.mongo_uri or not args.db:
        parser.error("Set COYOTE3_MONGO_URI and COYOTE3_DB or provide explicit overrides")
    with MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000) as client:
        result = migrate(client[args.db], apply=args.apply)
    print(f"{'Migrated' if args.apply else 'Would migrate'}: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
