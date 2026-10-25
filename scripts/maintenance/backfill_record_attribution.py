#!/usr/bin/env python3
"""Plan or apply evidence-based actor backfills for one mutable collection."""

import argparse
import json
import os
from collections.abc import Mapping
from typing import Any

from pymongo import MongoClient

from coyote3.contracts.schemas.registry import supported_collections


def attribution_changes(document: Mapping[str, Any], collection: str) -> dict[str, Any]:
    """Derive missing actors from stored evidence without guessing a current user.

    Args:
        document: Persisted document, never modified by this function.
        collection: Logical collection identity used to interpret author fields.

    Returns:
        Fields that differ from storage. Unknown actors remain null. Explicit
        installation flags identify system creation, not the last human editor.
    """
    installed = bool(document.get("system_managed") or document.get("system_installed"))
    creator = document.get("created_by")
    if installed:
        creator = "system"
    elif not creator:
        if collection == "samples":
            creator = document.get("ingested_by")
        elif collection in {"sample_comments", "finding_comments", "reports", "annotation"}:
            creator = document.get("author")
        if (
            not creator
            and collection in {"diagnoses", "diagnosis_associations"}
            and document.get("version") == 1
        ):
            creator = document.get("updated_by")
    updater = document.get("updated_by")
    if not updater and document.get("version") == 1:
        updater = creator
    target = {"created_by": creator, "updated_by": updater}
    return {
        key: value for key, value in target.items() if key not in document or document[key] != value
    }


def backfill(collection: Any, *, logical_name: str, apply: bool = False) -> dict[str, int]:
    """Inspect records and optionally update attribution with a concurrency check.

    Args:
        collection: MongoDB collection explicitly selected by the operator.
        logical_name: Supported mutable collection's contract name.
        apply: False only reports counts; True writes changed attribution fields.

    Returns:
        Counts without document identifiers or actor names.

    Raises:
        ValueError: The collection contains immutable revision evidence.
        RuntimeError: A record changed between inspection and its conditional update.
    """
    if logical_name.endswith("_revisions") or logical_name in {"reported_variants", "ingest_jobs"}:
        raise ValueError("Immutable historical evidence must not be rewritten")
    counts = {"inspected": 0, "planned": 0, "updated": 0, "unknown_creators": 0}
    projection = {
        key: 1
        for key in (
            "created_by",
            "updated_by",
            "system_managed",
            "system_installed",
            "version",
            "author",
            "ingested_by",
            "revision_hash",
            "diagnosis_id",
            "asp_id",
        )
    }
    for document in collection.find({}, projection):
        if "revision_hash" in document:
            raise ValueError("Immutable revision evidence must not be rewritten")
        counts["inspected"] += 1
        changes = attribution_changes(document, logical_name)
        if (
            not changes.get("created_by", document.get("created_by"))
            and logical_name in {"diagnoses", "diagnosis_associations"}
            and document.get("diagnosis_id")
        ):
            first_selector = {"diagnosis_id": document["diagnosis_id"], "version": 1}
            if logical_name == "diagnosis_associations":
                first_selector["asp_id"] = document.get("asp_id")
            first = collection.find_one(first_selector, {"created_by": 1, "updated_by": 1})
            if first and (first.get("created_by") or first.get("updated_by")):
                changes["created_by"] = first.get("created_by") or first["updated_by"]
        if not changes.get("created_by", document.get("created_by")):
            counts["unknown_creators"] += 1
        if not changes:
            continue
        counts["planned"] += 1
        if apply:
            selector = {"_id": document["_id"]}
            for key in projection:
                selector[key] = (
                    {"$eq": document[key], "$exists": True}
                    if key in document
                    else {"$exists": False}
                )
            result = collection.update_one(selector, {"$set": changes})
            if result.matched_count != 1:
                raise RuntimeError("A record changed during backfill; inspect and rerun the plan")
            counts["updated"] += 1
    return counts


def main() -> None:
    """Run a per-collection plan, writing only when explicitly requested."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri-env", default="COYOTE3_MONGO_URI")
    parser.add_argument("--database", required=True)
    parser.add_argument("--collection", required=True, choices=supported_collections())
    parser.add_argument("--storage-collection", help="Configured physical name, if different.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    uri = os.environ.get(args.mongo_uri_env)
    if not uri:
        parser.error("The selected MongoDB URI environment variable is not set")
    with MongoClient(uri, serverSelectionTimeoutMS=5000) as client:
        result = backfill(
            client[args.database][args.storage_collection or args.collection],
            logical_name=args.collection,
            apply=args.apply,
        )
    print(json.dumps({"mode": "apply" if args.apply else "plan", **result}))


if __name__ == "__main__":
    main()
