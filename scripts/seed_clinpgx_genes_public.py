#!/usr/bin/env python3
"""Seed the ClinPGx public gene cache from the official genes.tsv zip export."""

from __future__ import annotations

import argparse
import os
import tomllib
from pathlib import Path

from pymongo import MongoClient

from api.config.mongo import configured_mongo_uri
from api.config.paths import COLLECTIONS_CONFIG_PATH
from api.infra.knowledgebase.clinpgx_public import ClinPgxPublicRepository


class _Adapter:
    """Minimal adapter surface required by ClinPgxPublicRepository."""

    def __init__(self, collection):
        """Expose the supplied collection under the repository's expected attribute.

        Args:
            collection: MongoDB collection holding the public ClinPGx gene cache.
        """
        self.clinpgx_genes_public_collection = collection


def collection_name(config: dict) -> str:
    """Resolve the ClinPGx collection name from the API collection config."""
    db_collections = config.get("knowledgebase", {})
    return db_collections.get("clinpgx_genes_public_collection", "clinpgx_genes_public")


def main() -> int:
    """Import the selected ClinPGx gene ZIP into the configured public cache.

    Returns:
        Zero after printing total, matched, modified, and upserted record counts.

    Raises:
        SystemExit: CLI parsing exits or MongoDB URI or database settings are missing.
        FileNotFoundError: The supplied ZIP path does not exist.
        OSError: The collection configuration or gene archive cannot be read.
        zipfile.BadZipFile: The input is not a valid ZIP archive.
        KeyError: The archive does not contain ``genes.tsv``.
        pymongo.errors.PyMongoError: Index creation or gene-cache writes fail.

    Notes:
        Ensures repository indexes and imports records into the mapped knowledgebase
        collection. This command has no dry-run mode.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip",
        required=True,
        help="Path to ClinPGx genes zip export.",
    )
    parser.add_argument("--mongo-uri", default=configured_mongo_uri(os.environ, "knowledgebase"))
    parser.add_argument("--db", default=os.getenv("KNOWLEDGEBASE_DB", ""))
    args = parser.parse_args()
    if not args.mongo_uri:
        parser.error("--mongo-uri or KNOWLEDGEBASE_MONGO_URI is required")
    if not args.db:
        parser.error("--db or KNOWLEDGEBASE_DB is required")

    zip_path = Path(args.zip)
    if not zip_path.exists():
        raise FileNotFoundError(f"ClinPGx gene zip not found: {zip_path}")

    with COLLECTIONS_CONFIG_PATH.open("rb") as handle:
        config = tomllib.load(handle)
    client = MongoClient(args.mongo_uri)
    database = client[args.db]
    repository = ClinPgxPublicRepository(_Adapter(database[collection_name(config)]))
    repository.ensure_indexes()
    result = repository.import_gene_zip(zip_path)
    print(
        "clinpgx_genes_public seeded: "
        f"total={result['total']} matched={result['matched']} "
        f"modified={result['modified']} upserted={result['upserted']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
