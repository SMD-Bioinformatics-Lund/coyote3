#!/usr/bin/env python3
"""Capture an immutable baseline for clinical rule documents created before revision history."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.contracts.schemas.clinical_rules import ClinicalRuleSetDoc  # noqa: E402
from api.infra.mongo.repositories.clinical_rule_sets import (  # noqa: E402
    build_revision_snapshot,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", required=True, help="MongoDB URI with readWrite access")
    parser.add_argument("--db", required=True, help="Coyote3 application database name")
    parser.add_argument("--actor", required=True, help="Operator identity recorded on baselines")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count without writing")
    return parser.parse_args()


def capture_missing_baselines(db, *, actor: str, dry_run: bool) -> tuple[int, int]:
    """Create one current-state baseline per rule-set version when none exists."""
    mapping = load_collection_section("primary")
    rules = db[mapping["clinical_rule_sets_collection"]]
    revisions = db[mapping["clinical_rule_revisions_collection"]]
    if not dry_run:
        revisions.create_index(
            [("rule_set_oid", 1), ("revision", 1)],
            name="clinical_rule_oid_revision_unique",
            unique=True,
        )
    captured = 0
    unchanged = 0
    occurred_at = datetime.now(timezone.utc)
    for raw_document in rules.find({}).sort("_id", 1):
        document = ClinicalRuleSetDoc.model_validate(raw_document).model_dump(
            mode="python", by_alias=True, exclude_none=True
        )
        rule_set_oid = str(document["_id"])
        if revisions.count_documents({"rule_set_oid": rule_set_oid}, limit=1):
            unchanged += 1
            continue
        snapshot = build_revision_snapshot(
            document,
            action="baseline_captured",
            actor=actor,
            occurred_at=occurred_at,
            reason="Initial immutable baseline captured from the current rule document",
            previous_revision_hash=None,
        )
        if not dry_run:
            try:
                revisions.insert_one(snapshot)
            except DuplicateKeyError:
                unchanged += 1
                continue
        captured += 1
    return captured, unchanged


def main() -> int:
    args = parse_args()
    actor = args.actor.strip()
    if not actor:
        raise SystemExit("--actor must not be empty")
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    try:
        client.admin.command("ping")
        captured, unchanged = capture_missing_baselines(
            client[args.db], actor=actor, dry_run=args.dry_run
        )
    finally:
        client.close()
    mode = "would capture" if args.dry_run else "captured"
    print(f"[ok] {mode} {captured} clinical rule baselines; {unchanged} already preserved")
    print("[info] revisions before each baseline cannot be reconstructed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
