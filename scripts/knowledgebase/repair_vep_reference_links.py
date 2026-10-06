#!/usr/bin/env python3
"""Repair VEP documentation links and cache version labels, without changing definitions."""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from pathlib import Path

from bson import BSON
from dotenv import dotenv_values
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402
from scripts.knowledgebase.update_vep_metadata import SEED, reference_links  # noqa: E402


def corrections(document: dict) -> dict:
    """Build targeted field updates, retaining all clinical definitions and image bytes.

    Args:
        document: Existing VEP reference, including its major-release identifier.

    Returns:
        MongoDB dotted field paths whose values need correction.

    Raises:
        ValueError: The document's release has no reviewed archive mapping.
    """
    release = document["vep_id"]
    changes = {
        key: value
        for key, value in reference_links(int(release)).items()
        if document.get(key) != value
    }
    for build, metadata in document.get("db_info", {}).items():
        published = metadata.get("published_sources") or {}
        if published.get("Ensembl database version") == "[[SPECIESDEFS::ENSEMBL_VERSION]]":
            changes[f"db_info.{build}.published_sources.Ensembl database version"] = release
    return changes


def install(collection, backup: Path) -> int:
    """Back up and correct existing releases in a single transaction.

    Args:
        collection: Configured VEP metadata collection with maintenance write access.
        backup: New owner-readable BSON backup; an existing file is never overwritten.

    Returns:
        Number of corrected documents.

    Raises:
        RuntimeError: Another writer changes a document after backup.
        ValueError: A release cannot be mapped to an archive.
    """
    original = list(collection.find({}))
    changes = [(row, corrections(row)) for row in original]
    with backup.open("xb") as stream:
        os.chmod(backup, 0o600)
        for row in original:
            stream.write(BSON.encode(row))

    def update(session):
        """Check backed-up documents and apply only planned fields in this session."""
        for row, fields in changes:
            if collection.find_one({"_id": row["_id"]}, session=session) != row:
                raise RuntimeError("VEP metadata changed after backup")
            if fields:
                collection.update_one({"_id": row["_id"]}, {"$set": fields}, session=session)

    run_transaction(collection.database.client, update)
    return sum(bool(fields) for _, fields in changes)


def update_seed(path: Path = SEED) -> int:
    """Apply the same targeted repairs to the compressed reference seed.

    Args:
        path: Existing gzip NDJSON seed, replaced atomically after validation.

    Returns:
        Number of corrected seed records.
    """
    with gzip.open(path, "rt") as stream:
        documents = list(map(json.loads, stream))
    count = 0
    for row in documents:
        fields = corrections(row)
        count += bool(fields)
        for field, value in fields.items():
            target = row
            parts = field.split(".")
            for part in parts[:-1]:
                target = target[part]
            target[parts[-1]] = value
    payload = "".join(json.dumps(row) + "\n" for row in documents)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(gzip.compress(payload.encode(), mtime=0))
    temporary.replace(path)
    return count


def main() -> int:
    """Run an explicit database repair or seed repair, defaulting to neither.

    Returns:
        Zero after requested repairs complete.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--update-seed", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.backup:
        parser.error("--apply requires --backup")
    if args.apply:
        config = {**(dotenv_values(args.env_file) if args.env_file else {}), **os.environ}
        with MongoClient(
            config["KNOWLEDGEBASE_MONGO_URI"], serverSelectionTimeoutMS=10000
        ) as client:
            name = load_collection_section("knowledgebase")["vep_metadata_collection"]
            count = install(client[config["KNOWLEDGEBASE_DB"]][name], args.backup)
            print(f"Corrected {count} database references")
    if args.update_seed:
        print(f"Corrected {update_seed()} seed references")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
