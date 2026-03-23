#!/usr/bin/env python3
"""Repair baseline seed metadata for center baseline collections."""

from __future__ import annotations

import argparse

from pymongo import MongoClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill required defaults for baseline center collections."
    )
    parser.add_argument("--mongo-uri", required=True, help="Mongo URI with write access")
    parser.add_argument("--db", default="coyote3", help="Application DB name")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    client.admin.command("ping")
    db = client[args.db]

    repaired = 0

    for collection in ("asp_configs", "assay_specific_panels", "insilico_genelists"):
        result = db[collection].update_many(
            {"is_active": {"$exists": False}},
            {"$set": {"is_active": True}},
        )
        repaired += int(result.modified_count)

    print(f"[ok] baseline repair completed; documents touched: {repaired}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
