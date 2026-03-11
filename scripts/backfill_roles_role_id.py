#!/usr/bin/env python3
"""
Backfill explicit roles.role_id business key.

Rules:
- Keep existing role_id when present/non-empty.
- Else set role_id from _id (normalized lower-case).
"""

from __future__ import annotations

import argparse
from typing import Any

from pymongo import MongoClient
from pymongo.errors import PyMongoError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill roles.role_id")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    parser.add_argument("--db", default="coyote3")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def _normalize(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    return normalized or None


def main() -> int:
    args = parse_args()
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    try:
        client.admin.command("ping")
    except PyMongoError as exc:
        print(f"[error] Mongo connection failed: {exc}")
        return 2

    col = client[args.db]["roles"]
    scanned = 0
    updated = 0
    failed = 0

    for doc in col.find({}, {"_id": 1, "role_id": 1}):
        scanned += 1
        role_id = _normalize(doc.get("role_id")) or _normalize(doc.get("_id"))
        if not role_id:
            continue
        if _normalize(doc.get("role_id")) == role_id:
            continue

        if args.dry_run:
            updated += 1
            print(f"[dry-run] _id={doc.get('_id')} role_id -> {role_id!r}")
            continue

        try:
            result = col.update_one({"_id": doc.get("_id")}, {"$set": {"role_id": role_id}})
            if result.modified_count:
                updated += 1
        except PyMongoError as exc:
            failed += 1
            print(f"[error] update failed for _id={doc.get('_id')}: {exc}")

    print(f"[done] scanned={scanned} updated={updated} failed={failed} dry_run={args.dry_run}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
