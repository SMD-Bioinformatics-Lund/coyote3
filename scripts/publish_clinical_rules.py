#!/usr/bin/env python3
"""Validate and publish one clinical reporting YAML file as an immutable release."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tomllib
from pathlib import Path

from pymongo import MongoClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.application.reporting.clinical_rules.publisher import ClinicalRulePublisher  # noqa: E402
from api.infra.mongo.repositories.clinical_rule_sets import (  # noqa: E402
    ClinicalRuleSetRepository,
)


class _Adapter:
    """Minimal adapter required by the clinical-rule repository."""

    def __init__(self, collection):
        self.clinical_rule_sets_collection = collection


def _collection_name(db_name: str) -> str:
    config_path = REPO_ROOT / "api/config/coyote3_collections.toml"
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)
    try:
        return str(config[db_name]["clinical_rule_sets_collection"])
    except KeyError as exc:
        raise ValueError(
            f"clinical_rule_sets_collection is not configured for database '{db_name}'"
        ) from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI"))
    parser.add_argument("--db", default=os.getenv("COYOTE3_DB"))
    parser.add_argument("--published-by", required=True)
    args = parser.parse_args()
    if not args.mongo_uri:
        parser.error("--mongo-uri or MONGO_URI is required")
    if not args.db:
        parser.error("--db or COYOTE3_DB is required")

    client = MongoClient(args.mongo_uri)
    repository = ClinicalRuleSetRepository(_Adapter(client[args.db][_collection_name(args.db)]))
    repository.ensure_indexes()
    release = ClinicalRulePublisher(repository).publish(
        args.source,
        published_by=args.published_by,
    )
    print(
        json.dumps(
            {
                "release_id": str(release.id_),
                "rule_set_id": release.rule_set_id,
                "version": release.version,
                "content_hash": release.content_hash,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
