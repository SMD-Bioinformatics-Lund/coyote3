#!/usr/bin/env python3
"""
Backfill explicit users.user_id business key.

Rules:
- Keep existing user_id as-is when present/non-empty.
- Else set user_id from _id.
- Else fallback to username, then email.

The script is idempotent and can be run repeatedly.
"""

from __future__ import annotations

import argparse
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill users.user_id")
    parser.add_argument(
        "--mongo-uri",
        default="mongodb://localhost:27017",
        help="Mongo URI (default: mongodb://localhost:27017)",
    )
    parser.add_argument(
        "--db",
        default="coyote3",
        help="Database name (default: coyote3)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing",
    )
    return parser.parse_args()


def _normalize(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _resolve_user_id(doc: dict[str, Any]) -> str | None:
    for field in ("user_id", "_id", "username", "email"):
        resolved = _normalize(doc.get(field))
        if resolved:
            return resolved
    return None


def main() -> int:
    args = parse_args()
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        print(f"[error] Mongo connection failed: {exc}")
        return 2

    col = client[args.db]["users"]
    scanned = 0
    updated = 0
    skipped = 0
    failed = 0

    for doc in col.find({}, {"_id": 1, "user_id": 1, "username": 1, "email": 1}):
        scanned += 1
        target_user_id = _resolve_user_id(doc)
        if not target_user_id:
            skipped += 1
            print(f"[warn] skipped user with unresolved identity: _id={doc.get('_id')}")
            continue

        current_user_id = _normalize(doc.get("user_id"))
        if current_user_id == target_user_id:
            continue

        if args.dry_run:
            updated += 1
            print(f"[dry-run] _id={doc.get('_id')} user_id: {current_user_id!r} -> {target_user_id!r}")
            continue

        try:
            result = col.update_one({"_id": doc.get("_id")}, {"$set": {"user_id": target_user_id}})
            if result.modified_count:
                updated += 1
            else:
                failed += 1
                print(f"[warn] no document modified for _id={doc.get('_id')}")
        except PyMongoError as exc:
            failed += 1
            print(f"[error] update failed for _id={doc.get('_id')}: {exc}")

    print(
        f"[done] scanned={scanned} updated={updated} skipped={skipped} failed={failed} dry_run={args.dry_run}"
    )
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
