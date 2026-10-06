#!/usr/bin/env python3
"""Validate or transactionally insert one migration bundle into an isolated local target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bson import decode_file_iter
from pymongo import MongoClient
from pymongo.uri_parser import parse_uri

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402
from scripts.migration_common.offline import digest, read_json  # noqa: E402
from scripts.migration_common.run_report import write_report  # noqa: E402
from scripts.migration_common.target_catalog import (  # noqa: E402
    read_target_catalog,
    validate_plan_scope,
)
from scripts.upgrade_from_v3.clinical_documents import CLINICAL_COLLECTIONS  # noqa: E402

ALLOWED_TARGETS = set(CLINICAL_COLLECTIONS)


def guard_target(uri: str, database: str) -> None:
    """Reject production namespaces and require an explicit local migration database.

    Args:
        uri: Explicit destination URI; SRV, remote hosts, and the production tunnel port
            are not accepted. No application environment file is loaded.
        database: Destination name beginning coyote4_migration_.

    Raises:
        ValueError: The endpoint or namespace is outside the offline migration scope.
    """
    if not re.fullmatch(r"coyote4_migration_[A-Za-z0-9_]+", database):
        raise ValueError("Destination must use the coyote4_migration_ namespace")
    if not uri.startswith("mongodb://"):
        raise ValueError("Only an explicit local MongoDB URI is supported")
    parsed = parse_uri(uri)
    if len(parsed["nodelist"]) != 1:
        raise ValueError("Use one direct local destination endpoint")
    if parsed.get("database") not in (None, database):
        raise ValueError("URI database and explicit destination disagree")
    if any(
        host not in {"localhost", "127.0.0.1", "::1"} or port == 28803
        for host, port in parsed["nodelist"]
    ):
        raise ValueError("Only a local isolated destination is allowed; production tunnel refused")


def load_bundle(path: Path) -> dict[str, list[dict]]:
    """Verify every manifest hash, count, identity, and current collection contract."""
    manifest = read_json(path / "manifest.json")
    if manifest.get("format") != 1 or not isinstance(manifest.get("collections"), dict):
        raise ValueError("Unsupported or incomplete bundle")
    plan = {}
    for collection, expected in manifest["collections"].items():
        if collection not in ALLOWED_TARGETS:
            raise ValueError("Bundle includes a collection outside migration scope")
        if manifest.get("provenance", {}).get("source_version") == 2 and collection in {
            "d4_coverage",
            "d4_coverage_blacklist",
        }:
            raise ValueError("V2 bundles cannot contain D4 coverage collections")
        file = path / f"{collection}.bson"
        if file.is_symlink():
            raise ValueError("Bundle files cannot be symbolic links")
        with file.open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
            stream.seek(0)
            rows = list(decode_file_iter(stream))
        if checksum != expected["sha256"] or len(rows) != expected["count"]:
            raise ValueError("Bundle checksum or count differs from its manifest")
        ids = set()
        for row in rows:
            if row.get("_id") is None or str(row["_id"]) in ids:
                raise ValueError("Missing or duplicate bundle identity")
            ids.add(str(row["_id"]))
            COLLECTION_MODEL_ADAPTERS[collection].validate_python(row)
        plan[collection] = rows
    return plan


def check_sample_scope(target: Any, sample: dict, session: Any = None) -> None:
    """Require a preinstalled ASP and exactly matching ASPC before sample insertion."""
    if not target.assay_specific_panels.find_one({"asp_id": sample["asp_id"]}, session=session):
        raise ValueError("Install destination ASP configuration before samples")
    aspc = target.asp_configs.find_one({"_id": sample.get("current_aspc_id")}, session=session)
    if aspc is None:
        raise ValueError("Sample must bind an installed destination ASPC")
    for field, value in {
        "asp_id": sample["asp_id"],
        "environment": sample["environment"],
        "asp_category": sample["omics_layer"],
        "subpanel_id": sample.get("subpanel_id") or "base",
    }.items():
        if aspc.get(field, "base" if field == "subpanel_id" else None) != value:
            raise ValueError("Destination ASPC scope differs from the sample")


def apply_plan(
    target: Any,
    plan: dict[str, list[dict]],
    *,
    apply: bool = False,
    expected_samples: dict[str, str] | None = None,
    expected_catalog_digest: str | None = None,
) -> dict:
    """Insert an idempotent bundle with conflict checks repeated inside one transaction.

    Args:
        target: Isolated target database. The CLI validates its endpoint before connecting.
        plan: Verified BSON bundle, bounded to one sample or one shared resource batch.
        apply: False returns planned counts without writes; True requires transactions.
        expected_samples: For a metadata patch, exact prior sample hashes. None inserts only.
        expected_catalog_digest: Required target snapshot fingerprint in CLI-generated runs.

    Returns:
        Insert counts and whether the transaction was applied.

    Raises:
        ValueError: Existing clinical/configuration records conflict or scope is missing.
        RuntimeError: Post-commit verification fails; the destination must remain offline.
    """
    if set(plan) - ALLOWED_TARGETS:
        raise ValueError("Destination collection outside migration scope")
    if expected_samples is not None and (
        set(plan) != {"samples"}
        or set(expected_samples) != {str(row["_id"]) for row in plan["samples"]}
    ):
        raise ValueError("Metadata patch scope differs from expected sample identities")

    def pending(session: Any = None) -> dict[str, list[dict]]:
        """Recheck scope and existing identities in the transaction's snapshot."""
        if expected_catalog_digest is not None:
            catalog = read_target_catalog(target, session=session)
            if catalog["sha256"] != expected_catalog_digest:
                raise ValueError("Target configuration changed since conversion; repeat preflight")
            validate_plan_scope(catalog, plan)
        for sample in plan.get("samples", []):
            check_sample_scope(target, sample, session)
        result = {}
        for collection, rows in plan.items():
            result[collection] = []
            for row in rows:
                current = target[collection].find_one({"_id": row["_id"]}, session=session)
                if expected_samples is not None:
                    if current is None:
                        raise ValueError(
                            "Metadata backfill requires an existing destination sample"
                        )
                    if digest(current) == digest(row):
                        continue
                    if digest(current) != expected_samples[str(row["_id"])]:
                        raise ValueError("Destination sample changed since the backfill baseline")
                    before = deepcopy(current)
                    after = deepcopy(row)
                    for item in (before, after):
                        for key in ("case", "control"):
                            if isinstance(item.get(key), dict):
                                item[key].pop("reads", None)
                                item[key].pop("sequencing_run", None)
                                if not item[key]:
                                    item.pop(key)
                    if digest(before) != digest(after):
                        raise ValueError("Metadata patch attempts unrelated changes")
                    for key in ("case", "control"):
                        for field in ("reads", "sequencing_run"):
                            previous = (current.get(key) or {}).get(field)
                            if previous is not None and previous != (row.get(key) or {}).get(field):
                                raise ValueError("Metadata patch cannot overwrite recorded values")
                    result[collection].append(row)
                    continue
                if current is not None and digest(current) != digest(row):
                    raise ValueError(
                        "Destination contains a conflicting record; no overwrite allowed"
                    )
                if current is None:
                    if collection == "samples" and target.samples.find_one(
                        {"name": row["name"]}, session=session
                    ):
                        raise ValueError(
                            "Destination sample name is already bound to another identity"
                        )
                    if collection == "anno_vep" and target.anno_vep.find_one(
                        {
                            "simple_id_hash": row["simple_id_hash"],
                            "vep_version": row["vep_version"],
                        },
                        session=session,
                    ):
                        raise ValueError("VEP evidence identity already exists under another ID")
                    result[collection].append(row)
        return result

    additions = pending()
    result = {
        "insert_counts": {key: len(rows) for key, rows in additions.items()},
        "applied": False,
    }
    if not apply:
        return result

    def write(session: Any) -> None:
        """Write only records whose identity and scope passed transaction-local preflight."""
        for name, rows in pending(session).items():
            if expected_samples is not None:
                for row in rows:
                    target.samples.replace_one({"_id": row["_id"]}, row, session=session)
            elif rows:
                target[name].insert_many(rows, session=session)

    run_transaction(target.client, write)
    for name, rows in plan.items():
        for row in rows:
            if digest(target[name].find_one({"_id": row["_id"]})) != digest(row):
                raise RuntimeError("Post-copy verification failed; keep destination offline")
    result["applied"] = True
    return result


def main() -> int:
    """Apply an operator-selected offline bundle without loading application credentials."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path, help="New private JSON report path")
    args = parser.parse_args()
    report_path = None
    plan = None
    failure = None
    details = {"operation": "apply" if args.apply else "target_preflight", "source_version": None}
    try:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        candidate = args.report or args.bundle / f"application-{stamp}.json"
        if candidate.exists() or candidate.with_suffix(".md").exists():
            raise FileExistsError("Run reports must use new paths")
        report_path = candidate
        uri = os.environ.get("COYOTE_MIGRATION_TARGET_URI", "")
        guard_target(uri, args.target_db)
        plan = load_bundle(args.bundle)
        provenance = read_json(args.bundle / "manifest.json").get("provenance", {})
        details.update({key: value for key, value in provenance.items() if key != "operation"})
        expected = provenance.get("expected_samples")
        target_digest = provenance.get("target_sha256")
        if not target_digest:
            raise ValueError("Bundle has no validated target catalog fingerprint")
        if provenance.get("operation") == "metadata_backfill" and expected is None:
            raise ValueError("Metadata backfill manifest has no baseline")
        with MongoClient(uri, serverSelectionTimeoutMS=5000, directConnection=True) as client:
            print(
                json.dumps(
                    apply_plan(
                        client[args.target_db],
                        plan,
                        apply=args.apply,
                        expected_samples=expected,
                        expected_catalog_digest=target_digest,
                    )
                )
            )
        return 0
    except Exception as error:
        failure = error
        # PyMongo and validation errors may contain URIs or complete clinical records.
        print(f"Bundle application stopped: {type(error).__name__}", file=sys.stderr)
        return 1
    finally:
        if report_path is not None:
            write_report(report_path, details, plan, failure)


if __name__ == "__main__":
    raise SystemExit(main())
