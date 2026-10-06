#!/usr/bin/env python3
"""Move inline VEP diagrams to content-addressed binary records and seed assets."""

import argparse
import gzip
import json
import os
import sys
from pathlib import Path

from dotenv import dotenv_values
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from scripts.knowledgebase.update_vep_diagrams import install  # noqa: E402
from scripts.knowledgebase.update_vep_metadata import SEED, diagram_document  # noqa: E402
from scripts.knowledgebase.vep_diagram_storage import seed_diagram, split_diagram  # noqa: E402


def embedded_diagrams(documents: list[dict]) -> dict[str, dict]:
    """Validate legacy inline diagrams before separating them from metadata.

    Args:
        documents: Installed references or bundled seed records.

    Returns:
        Only inline diagrams requiring migration, keyed by release.

    Raises:
        ValueError: Any original image is invalid or has an incorrect checksum.
    """
    diagrams = {}
    for row in documents:
        diagram = row.get("consequence_diagram") or {}
        if "data_base64" not in diagram:
            continue
        _, content = split_diagram(diagram)
        validated = diagram_document(content, diagram["source_url"], int(row["vep_id"]))
        if validated != diagram:
            raise ValueError(f"Inconsistent diagram metadata for release {row['vep_id']}")
        diagrams[row["vep_id"]] = validated
    return diagrams


def migrate_seed(path: Path = SEED) -> int:
    """Write binary seed assets before atomically removing embedded image strings.

    Args:
        path: Existing compressed VEP metadata seed.

    Returns:
        Number of migrated diagrams; zero on subsequent runs.
    """
    with gzip.open(path, "rt") as stream:
        rows = list(map(json.loads, stream))
    diagrams = embedded_diagrams(rows)
    for row in rows:
        if row["vep_id"] in diagrams:
            row["consequence_diagram"] = seed_diagram(diagrams[row["vep_id"]], path.parent)
    temporary = path.with_suffix(".tmp")
    temporary.write_bytes(
        gzip.compress("".join(json.dumps(r) + "\n" for r in rows).encode(), mtime=0)
    )
    temporary.replace(path)
    return len(diagrams)


def main() -> int:
    """Migrate only explicitly selected database or seed targets.

    Returns:
        Zero after successful migration.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--update-seed", action="store_true")
    args = parser.parse_args()
    if args.apply and not args.backup:
        parser.error("--apply requires a new --backup path")
    if args.apply:
        config = {**(dotenv_values(args.env_file) if args.env_file else {}), **os.environ}
        with MongoClient(
            config["KNOWLEDGEBASE_MONGO_URI"], serverSelectionTimeoutMS=10000
        ) as client:
            mapping = load_collection_section("knowledgebase")
            collection = client[config["KNOWLEDGEBASE_DB"]][mapping["vep_metadata_collection"]]
            diagrams = embedded_diagrams(list(collection.find({})))
            if diagrams:
                install(collection, diagrams, args.backup)
            print(f"Migrated {len(diagrams)} database diagrams")
    if args.update_seed:
        print(f"Migrated {migrate_seed()} seed diagrams")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
