#!/usr/bin/env python3
"""Helpers for seed payload count/payload generation used by shell workflows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    count_parser = subparsers.add_parser("count", help="Count docs for collection in seed dir")
    count_parser.add_argument("--seed-dir", required=True)
    count_parser.add_argument("--collection", required=True)

    payload_parser = subparsers.add_parser(
        "payload", help="Render bulk-ingest payload for collection"
    )
    payload_parser.add_argument("--seed-dir", required=True)
    payload_parser.add_argument("--collection", required=True)
    payload_parser.add_argument("--ignore-duplicates", action="store_true")
    return parser.parse_args()


def load_docs(seed_dir: Path, collection: str) -> list:
    path = seed_dir / f"{collection}.json"
    if not path.exists():
        return []
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, list) else []


def main() -> int:
    args = parse_args()
    seed_dir = Path(args.seed_dir)
    docs = load_docs(seed_dir, args.collection)

    if args.command == "count":
        print(len(docs))
        return 0

    payload = {"collection": args.collection, "documents": docs}
    if args.ignore_duplicates:
        payload["ignore_duplicates"] = True
    print(json.dumps(payload, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
