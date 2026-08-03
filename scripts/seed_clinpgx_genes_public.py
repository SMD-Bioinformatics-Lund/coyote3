#!/usr/bin/env python3
"""Seed the ClinPGx public gene cache from the official genes.tsv zip export."""

from __future__ import annotations

import argparse
import os
import tomllib
from pathlib import Path

from pymongo import MongoClient

from api.config.paths import COLLECTIONS_CONFIG_PATH
from api.infra.knowledgebase.clinpgx_public import ClinPgxPublicRepository


class _Adapter:
    """Minimal adapter surface required by ClinPgxPublicRepository."""

    def __init__(self, collection):
        self.clinpgx_genes_public_collection = collection


def collection_name(config: dict, db_name: str) -> str:
    """Resolve the ClinPGx collection name from the API collection config."""
    db_collections = config.get(db_name, {})
    return db_collections.get("clinpgx_genes_public_collection", "clinpgx_genes_public")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zip",
        required=True,
        help="Path to ClinPGx genes zip export.",
    )
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI", "mongodb://localhost:27017"))
    parser.add_argument("--db", default=os.getenv("COYOTE3_DB", "coyote3_dev"))
    args = parser.parse_args()

    zip_path = Path(args.zip)
    if not zip_path.exists():
        raise FileNotFoundError(f"ClinPGx gene zip not found: {zip_path}")

    with COLLECTIONS_CONFIG_PATH.open("rb") as handle:
        config = tomllib.load(handle)
    client = MongoClient(args.mongo_uri)
    database = client[args.db]
    repository = ClinPgxPublicRepository(_Adapter(database[collection_name(config, args.db)]))
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
