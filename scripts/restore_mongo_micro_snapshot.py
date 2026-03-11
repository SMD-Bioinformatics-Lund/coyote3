#!/usr/bin/env python3
"""
Restore a tiny Mongo snapshot created by create_mongo_micro_snapshot.py.

This script restores docs and indexes directly via PyMongo, so it works
for Docker Mongo containers exposed on a URI without requiring mongoimport.
"""

import argparse
import json
from pathlib import Path
from typing import Any

from bson import json_util
from pymongo import MongoClient
from pymongo.errors import PyMongoError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Restore Coyote3 Mongo micro snapshot.")
    parser.add_argument(
        "--mongo-uri",
        default="mongodb://localhost:27017",
        help="Mongo URI to restore into (default: mongodb://localhost:27017)",
    )
    parser.add_argument(
        "--snapshot-dir",
        default=".internal/mongo_micro_snapshot",
        help="Snapshot directory containing manifest.json",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop target collections before restore",
    )
    return parser.parse_args()


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json_util.loads(line))
    return rows


def _normalize_index_direction(value: Any) -> Any:
    if isinstance(value, dict):
        if "$numberInt" in value:
            return int(value["$numberInt"])
        if "$numberLong" in value:
            return int(value["$numberLong"])
        if "$numberDouble" in value:
            as_float = float(value["$numberDouble"])
            return int(as_float) if as_float.is_integer() else as_float
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _normalize_index_keys(key_doc: dict[str, Any]) -> list[tuple[str, Any]]:
    key_items: list[tuple[str, Any]] = []
    for field, direction in (key_doc or {}).items():
        key_items.append((field, _normalize_index_direction(direction)))
    return key_items


def restore_indexes(coll, index_rows: list[dict[str, Any]]) -> None:
    for idx in index_rows:
        if idx.get("name") == "_id_":
            continue
        key_doc = idx.get("key") or {}
        key_items = _normalize_index_keys(key_doc)
        options = {}
        for opt in ("name", "unique", "sparse", "expireAfterSeconds", "partialFilterExpression", "collation"):
            if opt in idx:
                options[opt] = idx[opt]
        try:
            coll.create_index(key_items, **options)
        except Exception as exc:
            print(
                f"[warn] skipped index on {coll.full_name}: "
                f"name={idx.get('name')} keys={key_items} reason={exc}"
            )


def main() -> int:
    args = parse_args()
    root = Path(args.snapshot_dir)
    manifest_file = root / "manifest.json"
    if not manifest_file.exists():
        print(f"[error] manifest not found: {manifest_file}")
        return 2

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    dbs = manifest.get("dbs") or {}
    if not isinstance(dbs, dict) or not dbs:
        print("[error] invalid or empty snapshot manifest")
        return 3

    try:
        client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
        client.admin.command("ping")
    except PyMongoError as exc:
        print(f"[error] Mongo connection failed: {exc}")
        return 4

    for db_name, collections in dbs.items():
        db = client[db_name]
        for coll_name, meta in (collections or {}).items():
            coll = db[coll_name]
            docs_file = root / meta["docs_file"]
            idx_file = root / meta["indexes_file"]
            docs = read_ndjson(docs_file)
            indexes = read_ndjson(idx_file)

            if args.drop:
                coll.drop()
                coll = db[coll_name]

            if docs:
                coll.insert_many(docs, ordered=False)
            restore_indexes(coll, indexes)
            print(f"[ok] restored {db_name}.{coll_name}: {len(docs)} docs")

    print("[done] restore complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
