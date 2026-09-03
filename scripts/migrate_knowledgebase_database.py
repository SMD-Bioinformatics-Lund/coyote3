#!/usr/bin/env python3
"""Move external knowledgebase collections into a dedicated MongoDB database."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tomllib
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from bson import BSON
from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.config.paths import COLLECTIONS_CONFIG_PATH  # noqa: E402

ONCOKB_PUBLIC_COLLECTION_KEY = "oncokb_public_collection"
FORBIDDEN_ONCOKB_FIELDS = ("sample_ids", "sample_names")
STAGING_PREFIX = "__coyote3_knowledgebase_migration__"
COPY_BATCH_SIZE = 1_000


def knowledgebase_collections(config_path: Path) -> dict[str, str]:
    """Return logical-to-physical collection names from the knowledgebase mapping."""
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    mapping = config.get("knowledgebase")
    if not isinstance(mapping, dict) or not mapping:
        raise ValueError(f"[knowledgebase] is missing or empty in {config_path}")
    values = [str(value) for value in mapping.values()]
    if len(values) != len(set(values)):
        raise ValueError("Knowledgebase collection names must be unique")
    return {str(key): str(value) for key, value in mapping.items()}


def transformed_documents(
    collection_key: str, documents: Iterable[dict[str, Any]]
) -> Iterator[dict[str, Any]]:
    """Remove fields that are forbidden in the dedicated knowledgebase database."""
    for document in documents:
        result = dict(document)
        if collection_key == ONCOKB_PUBLIC_COLLECTION_KEY:
            for field in FORBIDDEN_ONCOKB_FIELDS:
                result.pop(field, None)
        yield result


def collection_digest(collection: Collection, collection_key: str) -> tuple[int, str]:
    """Hash transformed documents in MongoDB's deterministic ObjectId order."""
    digest = hashlib.sha256()
    count = 0
    cursor = collection.find({}).sort("_id", ASCENDING)
    for document in transformed_documents(collection_key, cursor):
        encoded = BSON.encode(document)
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
        count += 1
    return count, digest.hexdigest()


def source_collection_options(database: Database, collection_name: str) -> dict[str, Any]:
    """Return portable collection creation options, including validators."""
    metadata = next(database.list_collections(filter={"name": collection_name}), None)
    if not metadata:
        return {}
    if metadata.get("type") != "collection":
        raise ValueError(
            f"Knowledgebase namespace is not a collection: {database.name}.{collection_name}"
        )
    options = dict(metadata.get("options") or {})
    allowed = {
        "capped",
        "changeStreamPreAndPostImages",
        "collation",
        "max",
        "size",
        "storageEngine",
        "validationAction",
        "validationLevel",
        "validator",
    }
    return {key: value for key, value in options.items() if key in allowed}


def copy_indexes(source: Collection, target: Collection) -> int:
    """Copy all non-_id indexes from source to a staging collection."""
    copied = 0
    for index in source.list_indexes():
        if index.get("name") == "_id_":
            continue
        keys = list(index["key"].items())
        options = {
            key: value
            for key, value in dict(index).items()
            if key not in {"key", "name", "ns", "v"}
        }
        target.create_index(keys, name=index["name"], **options)
        copied += 1
    return copied


def copy_documents(source: Collection, target: Collection, collection_key: str) -> int:
    """Stream transformed documents into the staging collection in bounded batches."""
    copied = 0
    batch: list[dict[str, Any]] = []
    for document in transformed_documents(collection_key, source.find({}).sort("_id", ASCENDING)):
        batch.append(document)
        if len(batch) == COPY_BATCH_SIZE:
            target.insert_many(batch, ordered=True)
            copied += len(batch)
            batch = []
    if batch:
        target.insert_many(batch, ordered=True)
        copied += len(batch)
    return copied


def verify_pair(
    source: Collection,
    target: Collection,
    collection_key: str,
) -> dict[str, Any]:
    """Verify transformed source and target counts and complete content digests."""
    source_count, source_digest = collection_digest(source, collection_key)
    target_count, target_digest = collection_digest(target, collection_key)
    result = {
        "source_count": source_count,
        "target_count": target_count,
        "source_sha256": source_digest,
        "target_sha256": target_digest,
        "verified": source_count == target_count and source_digest == target_digest,
    }
    if collection_key == ONCOKB_PUBLIC_COLLECTION_KEY:
        result["forbidden_target_documents"] = target.count_documents(
            {"$or": [{field: {"$exists": True}} for field in FORBIDDEN_ONCOKB_FIELDS]}
        )
        result["verified"] = result["verified"] and result["forbidden_target_documents"] == 0
    return result


def migrate_collection(
    source_db: Database,
    target_db: Database,
    collection_key: str,
    collection_name: str,
    *,
    apply: bool,
) -> dict[str, Any]:
    """Inspect, copy, and verify one configured knowledgebase collection."""
    source_names = set(source_db.list_collection_names())
    target_names = set(target_db.list_collection_names())
    result: dict[str, Any] = {"collection": collection_name, "logical_key": collection_key}
    if collection_name not in source_names:
        result.update(status="missing_source", source_count=0)
        return result

    source = source_db[collection_name]
    result["source_count"] = source.count_documents({})
    if collection_key == ONCOKB_PUBLIC_COLLECTION_KEY:
        result["source_documents_with_sample_fields"] = source.count_documents(
            {"$or": [{field: {"$exists": True}} for field in FORBIDDEN_ONCOKB_FIELDS]}
        )

    if collection_name in target_names:
        verification = verify_pair(source, target_db[collection_name], collection_key)
        result.update(verification)
        if not verification["verified"]:
            raise RuntimeError(f"Target differs from source: {target_db.name}.{collection_name}")
        result["status"] = "verified_existing"
        return result

    if not apply:
        result["status"] = "ready"
        return result

    staging_name = f"{STAGING_PREFIX}{collection_name}"
    if staging_name in target_names:
        raise RuntimeError(
            f"Staging collection already exists and requires operator review: "
            f"{target_db.name}.{staging_name}"
        )

    options = source_collection_options(source_db, collection_name)
    target_db.create_collection(staging_name, **options)
    staging = target_db[staging_name]
    try:
        result["copied_count"] = copy_documents(source, staging, collection_key)
        result["copied_indexes"] = copy_indexes(source, staging)
        verification = verify_pair(source, staging, collection_key)
        result.update(verification)
        if not verification["verified"]:
            raise RuntimeError(f"Staging verification failed for {collection_name}")
        staging.rename(collection_name, dropTarget=False)
    except Exception:
        result["status"] = "failed_staging_retained"
        raise
    result["status"] = "migrated"
    return result


def parse_args() -> argparse.Namespace:
    """Parse migration arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI", ""))
    parser.add_argument("--source-db", default=os.getenv("COYOTE3_DB", ""))
    parser.add_argument("--target-db", default=os.getenv("KNOWLEDGEBASE_DB", ""))
    parser.add_argument("--collections-config", type=Path, default=COLLECTIONS_CONFIG_PATH)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true", help="Copy and verify collections.")
    parser.add_argument(
        "--drop-source",
        action="store_true",
        help="Drop source collections only after every present source verifies in the target.",
    )
    parser.add_argument(
        "--confirm-drop-source",
        default="",
        metavar="DATABASE",
        help="Required source database name confirmation when --drop-source is used.",
    )
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Execute the guarded migration and return its non-sensitive report."""
    if not args.mongo_uri or not args.source_db or not args.target_db:
        raise ValueError("MONGO_URI, source database, and target database are required")
    if args.source_db == args.target_db:
        raise ValueError("Source and target databases must be different")
    if args.drop_source and not args.apply:
        raise ValueError("--drop-source requires --apply")
    if args.drop_source and args.confirm_drop_source != args.source_db:
        raise ValueError("--confirm-drop-source must exactly match --source-db")

    mapping = knowledgebase_collections(args.collections_config)
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=10_000)
    try:
        client.admin.command("ping")
        source_db = client[args.source_db]
        target_db = client[args.target_db]
        results = [
            migrate_collection(source_db, target_db, key, name, apply=args.apply)
            for key, name in mapping.items()
        ]

        present_results = [result for result in results if result["status"] != "missing_source"]
        all_verified = bool(present_results) and all(
            result.get("verified") for result in present_results
        )
        dropped: list[str] = []
        if args.drop_source:
            if not all_verified:
                raise RuntimeError(
                    "Source cleanup blocked because not every present collection verified"
                )
            for result in present_results:
                collection_name = str(result["collection"])
                source_db.drop_collection(collection_name)
                dropped.append(collection_name)

        return {
            "mode": "apply" if args.apply else "dry-run",
            "source_database": args.source_db,
            "target_database": args.target_db,
            "all_present_collections_verified": all_verified,
            "source_collections_dropped": dropped,
            "collections": results,
        }
    finally:
        client.close()


def main() -> int:
    """Run the command and optionally persist its report."""
    args = parse_args()
    try:
        report = run(args)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, default=str)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(f"{rendered}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
