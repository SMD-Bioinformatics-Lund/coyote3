#!/usr/bin/env python3
"""Repair malformed comment entries introduced by legacy nested $push writes.

This script rewrites documents where `comments` contains entries shaped like:
    {"$push": {"comments": {...canonical comment...}}}
into:
    {...canonical comment...}

Default scan mode:
    - configured sample/finding collections from `config/coyote3_collections.toml`
      for the selected DB (for example `cnvs_wgs` in `coyote_dev_3`).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

import toml
from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError


def _normalize_comment_entry(comment: Any) -> Any:
    if not isinstance(comment, dict):
        return comment
    push_doc = comment.get("$push")
    if isinstance(push_doc, dict):
        nested = push_doc.get("comments")
        if isinstance(nested, dict):
            return nested
    nested_comments = comment.get("comments")
    if isinstance(nested_comments, dict):
        return nested_comments
    return comment


def _normalize_comments(comments: Any) -> tuple[list[Any], bool]:
    if not isinstance(comments, list):
        return [], False
    changed = False
    out: list[Any] = []
    for item in comments:
        normalized = _normalize_comment_entry(item)
        if normalized is not item:
            changed = True
        out.append(normalized)
    return out, changed


def main() -> int:
    parser = argparse.ArgumentParser(description="Repair malformed nested comment entries.")
    parser.add_argument("--mongo-uri", default="mongodb://127.0.0.1:27017")
    parser.add_argument("--db", default="coyote3")
    parser.add_argument("--collections", nargs="+", default=None)
    parser.add_argument(
        "--collections-toml",
        default="config/coyote3_collections.toml",
        help="Path to collections TOML used to resolve default collection names.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply writes. Without this flag, script runs in dry-run mode.",
    )
    args = parser.parse_args()

    try:
        client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
        db = client[args.db]
        client.admin.command("ping")
    except PyMongoError as exc:
        print(f"[error] Mongo connection failed: {exc}", file=sys.stderr)
        return 2

    total_scanned = 0
    total_changed = 0

    collection_names = args.collections
    if not collection_names:
        try:
            collections_map = toml.load(args.collections_toml).get(args.db, {})
        except Exception as exc:
            print(f"[error] Failed to read collections TOML {args.collections_toml}: {exc}", file=sys.stderr)
            return 2
        keys = [
            "samples_collection",
            "variants_collection",
            "cnvs_collection",
            "transloc_collection",
            "fusions_collection",
        ]
        collection_names = [collections_map.get(key) for key in keys if collections_map.get(key)]
    collection_names = [name for name in collection_names if name]

    for name in collection_names:
        collection = db[name]
        ops: list[UpdateOne] = []
        scanned = 0
        changed = 0
        cursor = collection.find({"comments": {"$exists": True}}, {"comments": 1})
        for doc in cursor:
            scanned += 1
            comments, is_changed = _normalize_comments(doc.get("comments"))
            if not is_changed:
                continue
            changed += 1
            ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"comments": comments}}))
            if args.apply and len(ops) >= 500:
                collection.bulk_write(ops, ordered=False)
                ops.clear()

        if args.apply and ops:
            collection.bulk_write(ops, ordered=False)

        total_scanned += scanned
        total_changed += changed
        mode = "apply" if args.apply else "dry-run"
        print(f"[{mode}] {name}: scanned={scanned} changed={changed}")

    print(f"[done] scanned={total_scanned} changed={total_changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
