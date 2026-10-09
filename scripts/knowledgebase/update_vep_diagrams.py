#!/usr/bin/env python3
"""Download Ensembl diagrams for installed VEP releases, including release 103."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import httpx
from bson import BSON, json_util
from dotenv import dotenv_values
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.infra.mongo.repositories.knowledgebase_publications import (  # noqa: E402
    record_reference_publication,
)
from api.infra.mongo.transactions import run_transaction  # noqa: E402
from scripts.knowledgebase.update_vep_metadata import SEED, fetch_diagram  # noqa: E402
from scripts.knowledgebase.vep_diagram_storage import seed_diagram, store_diagram  # noqa: E402


def download(release: str, sha: str) -> dict:
    """Download a release-pinned Ensembl diagram without sending local data.

    Args:
        release: Major Ensembl release identifier.
        sha: Public-plugins commit belonging to that release.

    Returns:
        Validated diagram with source provenance.
    """
    return fetch_diagram(int(release), sha)[0]


def install(collection, diagrams: dict[str, dict], backup: Path) -> None:
    """Store binary assets and compact descriptors, preserving reference definitions.

    Args:
        collection: Knowledgebase VEP collection with maintenance write access.
        diagrams: Validated diagrams keyed by existing release identifier.
        backup: New owner-only BSON file containing original complete documents.

    Raises:
        ValueError: A requested release is not installed.
        RuntimeError: Another writer changed reference records after the backup.

    Notes:
        Binary assets and descriptors, including release 103, share one transaction.
    """
    query = {"vep_id": {"$in": list(diagrams)}}
    original = list(collection.find(query))
    if {row["vep_id"] for row in original} != set(diagrams):
        raise ValueError("All requested VEP releases must already be installed")
    with backup.open("xb") as stream:
        os.chmod(backup, 0o600)
        for row in original:
            stream.write(BSON.encode(row))

    def update(session):
        """Check original reference records and write diagrams in the supplied session."""
        current = list(collection.find(query, session=session))
        if sorted(current, key=lambda r: r["vep_id"]) != sorted(
            original, key=lambda r: r["vep_id"]
        ):
            raise RuntimeError("VEP metadata changed after backup")
        for release, diagram in diagrams.items():
            descriptor = store_diagram(collection.database, diagram, session)
            collection.update_one(
                {"vep_id": release}, {"$set": {"consequence_diagram": descriptor}}, session=session
            )
            record_reference_publication(
                collection.database, source="vep_diagrams", release=release, session=session
            )

    run_transaction(collection.database.client, update)


def main() -> int:
    """Download diagrams for seed releases; write database/seed only when requested.

    Returns:
        Zero after successful downloads and requested updates.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cpus", type=int, default=4)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--update-seed", action="store_true")
    args = parser.parse_args()
    if args.cpus < 1 or (args.apply and not args.backup):
        parser.error("Positive --cpus and --backup for --apply are required")
    with gzip.open(SEED, "rt") as stream:
        documents = list(map(json.loads, stream))
    response = httpx.get(
        "https://api.github.com/repos/Ensembl/public-plugins/git/matching-refs/heads/release/",
        timeout=60,
    )
    response.raise_for_status()
    refs = {row["ref"].rsplit("/", 1)[1]: row["object"]["sha"] for row in response.json()}
    with ThreadPoolExecutor(max_workers=args.cpus) as pool:
        futures = {
            row["vep_id"]: pool.submit(download, row["vep_id"], refs[row["vep_id"]])
            for row in documents
        }
        diagrams = {release: future.result() for release, future in futures.items()}
    args.output.write_text(json_util.dumps(diagrams))
    if args.apply:
        config = {**(dotenv_values(args.env_file) if args.env_file else {}), **os.environ}
        with MongoClient(
            config["KNOWLEDGEBASE_MONGO_URI"], serverSelectionTimeoutMS=10000
        ) as client:
            name = load_collection_section("knowledgebase")["vep_metadata_collection"]
            install(client[config["KNOWLEDGEBASE_DB"]][name], diagrams, args.backup)
    if args.update_seed:
        for row in documents:
            row["consequence_diagram"] = seed_diagram(diagrams[row["vep_id"]], SEED.parent)
        temporary = SEED.with_suffix(".tmp")
        temporary.write_bytes(
            gzip.compress(("".join(json.dumps(row) + "\n" for row in documents)).encode(), mtime=0)
        )
        temporary.replace(SEED)
    print(f"Validated {len(diagrams)} release-specific diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
