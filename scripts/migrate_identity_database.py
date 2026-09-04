#!/usr/bin/env python3
"""Move identity and security collections into the dedicated MongoDB database."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from pymongo import MongoClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.paths import COLLECTIONS_CONFIG_PATH  # noqa: E402
from scripts.migrate_knowledgebase_database import migrate_collection  # noqa: E402

STAGING_PREFIX = "__coyote3_identity_migration__"


def identity_collections(config_path: Path) -> dict[str, str]:
    """Return the configured identity and security collection mapping."""
    mapping = load_collection_section("identity", config_path=config_path)
    values = list(mapping.values())
    if len(values) != len(set(values)):
        raise ValueError("Identity collection names must be unique")
    return mapping


def parse_args() -> argparse.Namespace:
    """Parse migration arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI", ""))
    parser.add_argument("--source-db", default=os.getenv("COYOTE3_DB", ""))
    parser.add_argument("--target-db", default=os.getenv("IDENTITY_DB", ""))
    parser.add_argument("--collections-config", type=Path, default=COLLECTIONS_CONFIG_PATH)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--apply", action="store_true", help="Copy and verify collections.")
    parser.add_argument(
        "--drop-source",
        action="store_true",
        help="Drop source collections only after every present source verifies in the target.",
    )
    parser.add_argument(
        "--confirm-drop-source",
        default="",
        metavar="DATABASE",
        help="Required source database name confirmation when --drop-source is used.",
    )
    return parser.parse_args()


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Execute the guarded identity migration and return a non-sensitive report."""
    if not args.mongo_uri or not args.source_db or not args.target_db:
        raise ValueError("MONGO_URI, source database, and target database are required")
    if args.source_db == args.target_db:
        raise ValueError("Source and target databases must be different")
    if args.drop_source and not args.apply:
        raise ValueError("--drop-source requires --apply")
    if args.drop_source and args.confirm_drop_source != args.source_db:
        raise ValueError("--confirm-drop-source must exactly match --source-db")

    mapping = identity_collections(args.collections_config)
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=10_000)
    try:
        client.admin.command("ping")
        source_db = client[args.source_db]
        target_db = client[args.target_db]
        results = [
            migrate_collection(
                source_db,
                target_db,
                key,
                name,
                apply=args.apply,
                staging_prefix=STAGING_PREFIX,
            )
            for key, name in mapping.items()
        ]
        present_results = [result for result in results if result["status"] != "missing_source"]
        all_verified = bool(present_results) and all(
            result.get("verified") for result in present_results
        )
        dropped: list[str] = []
        if args.drop_source:
            if not all_verified:
                raise RuntimeError(
                    "Source cleanup blocked because not every present collection verified"
                )
            for result in present_results:
                collection_name = str(result["collection"])
                source_db.drop_collection(collection_name)
                dropped.append(collection_name)
        return {
            "mode": "apply" if args.apply else "dry-run",
            "source_database": args.source_db,
            "target_database": args.target_db,
            "all_present_collections_verified": all_verified,
            "source_collections_dropped": dropped,
            "collections": results,
        }
    finally:
        client.close()


def main() -> int:
    """Run the command and optionally persist its report."""
    args = parse_args()
    try:
        report = run(args)
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(report, indent=2, default=str)
    print(rendered)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(f"{rendered}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
