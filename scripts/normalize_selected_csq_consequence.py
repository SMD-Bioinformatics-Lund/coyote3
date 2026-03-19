#!/usr/bin/env python3
"""Normalize variants.INFO.selected_CSQ.Consequence into list form."""

from __future__ import annotations

import argparse
from typing import Any

from pymongo import MongoClient, UpdateOne


def _normalize_consequence(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, tuple) or isinstance(value, set):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [part.strip() for part in value.split("&") if part.strip()]
    if value in {None, ""}:
        return []
    text = str(value).strip()
    return [text] if text else []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize variants.INFO.selected_CSQ.Consequence to list[str]."
    )
    parser.add_argument(
        "--mongo-uri", required=True, help="Mongo URI, e.g. mongodb://localhost:27017"
    )
    parser.add_argument("--db", required=True, help="Database name")
    parser.add_argument(
        "--collection", default="variants", help="Collection name (default: variants)"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates. If omitted, command runs in dry-run mode.",
    )
    parser.add_argument("--batch-size", type=int, default=500, help="Bulk update batch size")
    args = parser.parse_args()

    client = MongoClient(args.mongo_uri)
    col = client[args.db][args.collection]

    query = {"INFO.selected_CSQ.Consequence": {"$exists": True}}
    projection = {"INFO.selected_CSQ.Consequence": 1}
    cursor = col.find(query, projection, no_cursor_timeout=True)

    scanned = 0
    changed = 0
    operations: list[UpdateOne] = []
    modified = 0

    try:
        for doc in cursor:
            scanned += 1
            selected_csq = (doc.get("INFO") or {}).get("selected_CSQ") or {}
            original = selected_csq.get("Consequence")
            normalized = _normalize_consequence(original)
            if original == normalized:
                continue

            changed += 1
            operations.append(
                UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": {"INFO.selected_CSQ.Consequence": normalized}},
                )
            )
            if args.apply and len(operations) >= args.batch_size:
                result = col.bulk_write(operations, ordered=False)
                modified += int(result.modified_count)
                operations.clear()
    finally:
        cursor.close()

    if args.apply and operations:
        result = col.bulk_write(operations, ordered=False)
        modified += int(result.modified_count)

    mode = "APPLY" if args.apply else "DRY_RUN"
    print(f"mode={mode} scanned={scanned} candidates={changed} modified={modified}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
