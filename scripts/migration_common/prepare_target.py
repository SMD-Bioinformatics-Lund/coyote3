#!/usr/bin/env python3
"""Read and validate preinstalled configuration from the isolated migration target."""

import argparse
import os
import sys
from pathlib import Path

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.migration_common.apply_bundle import guard_target  # noqa: E402
from scripts.migration_common.offline import private_json  # noqa: E402
from scripts.migration_common.target_catalog import read_target_catalog  # noqa: E402


def main() -> int:
    """Export a private catalog without modifying destination records or indexes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-db", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        uri = os.environ.get("COYOTE_MIGRATION_TARGET_URI", "")
        guard_target(uri, args.target_db)
        with MongoClient(uri, serverSelectionTimeoutMS=5000, directConnection=True) as client:
            catalog = read_target_catalog(client[args.target_db])
        private_json(args.output, catalog)
        print("Target configuration validated and exported; no database writes performed.")
        return 0
    except Exception as error:
        print(f"Target preflight stopped: {type(error).__name__}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
