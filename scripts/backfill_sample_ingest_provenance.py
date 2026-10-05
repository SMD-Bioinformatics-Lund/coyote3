#!/usr/bin/env python3
"""Recover initial sample attribution from durable creation-job receipts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from bson.json_util import dumps  # noqa: E402
from dotenv import dotenv_values  # noqa: E402

from api.application.ingest.jobs import sample_entry_source  # noqa: E402
from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.infra.mongo.connections import MongoConnections  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402

ATTRIBUTION_FIELDS = ("ingested_by", "ingest_source")


def plan_backfill(samples: list[dict], jobs: list[dict]) -> list[dict[str, Any]]:
    """Plan missing attribution fields using only successful initial creation receipts.

    Args:
        samples: Sample identifiers and current attribution fields.
        jobs: Durable job documents in ascending creation order, including results.

    Returns:
        Updates with optimistic selectors and previous field values for rollback.
        Missing evidence produces explicit nulls; existing non-null values are preserved.
    """
    evidence: dict[str, dict[str, Any]] = {}
    for job in jobs:
        if (
            job.get("state") != "succeeded"
            or job.get("kind") != "sample_bundle"
            or job.get("update_existing") is not False
        ):
            continue
        sample_id = (job.get("result") or {}).get("sample_id")
        if sample_id and job.get("submitted_by"):
            evidence.setdefault(
                str(sample_id),
                {"ingested_by": job["submitted_by"], "ingest_source": sample_entry_source(job)},
            )
    plan = []
    for sample in samples:
        recovered = evidence.get(str(sample["_id"]), {})
        updates = {}
        for field in ATTRIBUTION_FIELDS:
            if sample.get(field) is None:
                value = recovered.get(field)
                if field not in sample or value is not None:
                    updates[field] = value
        if not updates:
            continue
        selector: dict[str, Any] = {"_id": sample["_id"]}
        before = {}
        missing = []
        for field in updates:
            if field in sample:
                selector[field] = {"$eq": sample[field], "$exists": True}
                before[field] = sample[field]
            else:
                selector[field] = {"$exists": False}
                missing.append(field)
        plan.append({"selector": selector, "set": updates, "before": before, "missing": missing})
    return plan


def apply_backfill(collection: Any, plan: list[dict[str, Any]]) -> int:
    """Apply a precomputed plan atomically, rejecting concurrent attribution changes.

    Args:
        collection: Sample collection whose client owns the transaction.
        plan: Updates returned by plan_backfill; callers must save a backup before writing.

    Returns:
        Number of changed samples after commit.

    Raises:
        RuntimeError: A sample changed or disappeared after planning.
        pymongo.errors.PyMongoError: A database operation fails; the transaction aborts.
    """

    def apply(session):
        """Apply guarded updates in the transaction supplied by the collection client."""
        count = 0
        for change in plan:
            result = collection.update_one(
                change["selector"], {"$set": change["set"]}, session=session
            )
            if result.matched_count != 1:
                raise RuntimeError("Sample attribution changed after backfill planning")
            count += result.modified_count
        return count

    return run_transaction(collection.database.client, apply)


def main() -> int:
    """Preview or apply a backed-up attribution migration using one deployment environment.

    Returns:
        Zero after printing aggregate counts without sample identities or credentials.

    Raises:
        SystemExit: Required command-line options are missing.
        OSError: The environment or new backup file cannot be read or written.
        pymongo.errors.PyMongoError: Connecting, reading, or updating MongoDB fails.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.apply and args.backup is None:
        parser.error("--apply requires a new --backup file")
    connections = MongoConnections(dict(dotenv_values(args.env_file)))
    try:
        db = connections.databases["primary"]
        mapping = load_collection_section("primary")
        samples = db[mapping["samples_collection"]]
        jobs = db[mapping["ingest_jobs_collection"]]
        plan = plan_backfill(
            list(samples.find({}, dict.fromkeys(ATTRIBUTION_FIELDS, 1))),
            list(
                jobs.find(
                    {"state": "succeeded", "kind": "sample_bundle", "update_existing": False},
                    {
                        "state": 1,
                        "kind": 1,
                        "update_existing": 1,
                        "result.sample_id": 1,
                        "submitted_by": 1,
                        "staging_dir": 1,
                        "created_at": 1,
                    },
                ).sort("created_at", 1)
            ),
        )
        print(
            json.dumps(
                {
                    "planned": len(plan),
                    "recovered_actors": sum(
                        change["set"].get("ingested_by") is not None for change in plan
                    ),
                }
            )
        )
        if args.apply:
            with os.fdopen(
                os.open(args.backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w"
            ) as stream:
                stream.write(dumps(plan))
                stream.flush()
                os.fsync(stream.fileno())
            print(json.dumps({"updated": apply_backfill(samples, plan)}))
        return 0
    finally:
        connections.close()


if __name__ == "__main__":
    raise SystemExit(main())
