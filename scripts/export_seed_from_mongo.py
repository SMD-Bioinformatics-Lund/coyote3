#!/usr/bin/env python3
"""Export center seed JSON from a MongoDB database.

Exports selected collections into the same shape used by
`scripts/bootstrap_center_collections.sh` seed files.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from bson import json_util
from pymongo import MongoClient

DEFAULT_COLLECTIONS = [
    "permissions",
    "roles",
    "asp_configs",
    "assay_specific_panels",
    "insilico_genelists",
]

REFERENCE_COLLECTIONS = [
    "refseq_canonical",
    "hgnc_genes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export selected Mongo collections to center seed JSON."
    )
    parser.add_argument("--mongo-uri", required=True, help="Mongo connection URI")
    parser.add_argument("--db", default="coyote3", help="Database name")
    parser.add_argument(
        "--out-file",
        default=".internal/prod_baseline_seed.json",
        help="Output JSON file path",
    )
    parser.add_argument(
        "--include-reference",
        action="store_true",
        help="Include large reference collections (refseq_canonical, hgnc_genes)",
    )
    parser.add_argument(
        "--include-users",
        action="store_true",
        help="Include users collection in output (bootstrap script still skips users by default)",
    )
    return parser.parse_args()


def _to_plain(value: Any) -> Any:
    """Convert bson types to JSON-safe values."""
    dumped = json_util.dumps(value)
    return json.loads(dumped)


def _strip_top_level_id(doc: dict[str, Any]) -> dict[str, Any]:
    cleaned = dict(doc)
    cleaned.pop("_id", None)
    return cleaned


def _sorted_docs(collection: str, docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return deterministically sorted docs by common business key."""
    key_candidates = [
        "permission_id",
        "role_id",
        "aspc_id",
        "asp_id",
        "isgl_id",
        "gene",
        "hgnc_id",
        "email",
        "username",
    ]
    sort_key = next((k for k in key_candidates if docs and k in docs[0]), None)
    if sort_key:
        return sorted(docs, key=lambda d: str(d.get(sort_key, "")))
    return docs


def main() -> int:
    args = parse_args()
    out_path = Path(args.out_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    collections = list(DEFAULT_COLLECTIONS)
    if args.include_reference:
        collections.extend(REFERENCE_COLLECTIONS)
    if args.include_users:
        collections.append("users")

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    client.admin.command("ping")
    db = client[args.db]

    payload: dict[str, list[dict[str, Any]]] = {}
    for name in collections:
        docs = []
        for raw_doc in db[name].find({}):
            plain = _to_plain(raw_doc)
            docs.append(_strip_top_level_id(plain))
        docs = _sorted_docs(name, docs)
        payload[name] = docs
        print(f"[ok] exported {name}: {len(docs)} docs")

    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[ok] wrote seed file: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
