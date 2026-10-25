#!/usr/bin/env python3
"""Verify installed HGNC and VEP references before preparing clinical migration bundles."""

import argparse
import hashlib
import os
import sys
from pathlib import Path
from typing import Any

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from coyote3.contracts.schemas.registry import COLLECTION_MODEL_ADAPTERS  # noqa: E402
from scripts.migration_common.apply_bundle import guard_target  # noqa: E402
from scripts.migration_common.offline import digest, private_json, read_json  # noqa: E402


def reference_snapshot(database: Any, version: str) -> dict:
    """Read and validate both reference collections without changing MongoDB.

    Args:
        database: Isolated knowledgebase MongoDB database handle.
        version: Required historical VEP release identifier, for example 103.

    Returns:
        Content fingerprints, counts and the verified VEP release.

    Raises:
        ValueError: Either collection is empty or the required VEP metadata is absent.
        pydantic.ValidationError: An installed reference violates its current contract.
    """
    collections = {}
    releases = set()
    for name in ("vep_metadata", "hgnc_genes"):
        count = 0
        checksum = hashlib.sha256()
        for row in database[name].find({}).sort("_id", 1):
            COLLECTION_MODEL_ADAPTERS[name].validate_python(row)
            checksum.update(digest(row).encode("ascii"))
            count += 1
            if name == "vep_metadata":
                releases.add(str(row["vep_id"]))
        if not count:
            raise ValueError("Install nonempty vep_metadata and hgnc_genes before migration")
        collections[name] = {"count": count, "sha256": checksum.hexdigest()}
    if version not in releases:
        raise ValueError("Install the required historical VEP metadata release")
    payload = {"database": database.name, "vep_version": version, "collections": collections}
    return {"format": 1, **payload, "sha256": digest(payload)}


def verify_reference_snapshot(path: Path, version: str) -> dict:
    """Validate an earlier read-only reference preflight for the requested release.

    Args:
        path: Private snapshot produced by this script.
        version: Required VEP release, matching the shared annotation evidence reference.

    Returns:
        Verified reference provenance to include in migration manifests.

    Raises:
        ValueError: The snapshot is incomplete, altered, or for another release.
    """
    snapshot = read_json(path)
    payload = {key: value for key, value in snapshot.items() if key not in {"format", "sha256"}}
    if (
        snapshot.get("format") != 1
        or snapshot.get("sha256") != digest(payload)
        or snapshot.get("vep_version") != version
        or set(snapshot.get("collections", {})) != {"vep_metadata", "hgnc_genes"}
        or any(row.get("count", 0) <= 0 for row in snapshot["collections"].values())
    ):
        raise ValueError("A valid HGNC/VEP reference preflight is required")
    return snapshot


def main() -> int:
    """Write a private reference preflight using only read operations on the target."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-db", required=True, help="Isolated knowledgebase database")
    parser.add_argument("--vep-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        uri = os.environ.get("COYOTE_MIGRATION_KNOWLEDGEBASE_URI", "")
        guard_target(uri, args.target_db)
        with MongoClient(uri, serverSelectionTimeoutMS=5000, directConnection=True) as client:
            snapshot = reference_snapshot(client[args.target_db], args.vep_version)
        private_json(args.output, snapshot)
        print("HGNC and VEP references verified; no database writes performed.")
        return 0
    except Exception as error:
        print(f"Reference preflight stopped: {type(error).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
