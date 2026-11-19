#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Verify clinical audit chains and optionally compare an independently retained checkpoint."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from coyote_mongo.audit_checkpoints import archive_checkpoint, latest_checkpoint  # noqa: E402
from coyote_mongo.config.collections import load_collection_section  # noqa: E402
from coyote_mongo.config.endpoints import mongo_uri  # noqa: E402
from coyote_mongo.config.operational_collections import (  # noqa: E402
    get_audit_events_collection_name,  # noqa: E402
)
from coyote_mongo.repositories.audit_integrity import verify_chain  # noqa: E402
from pymongo import MongoClient  # noqa: E402
from pymongo.errors import PyMongoError  # noqa: E402


def main() -> int:
    """Read the configured identity database and print a credential-free verification result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint", type=Path, help="Trusted JSON from an earlier successful verification"
    )
    parser.add_argument(
        "--archive-directory",
        type=Path,
        help="Export successful verification to an independently retained archive mount",
    )
    parser.add_argument(
        "--check-schedule",
        action="store_true",
        help="Require a fresh scheduled export and --checkpoint; perform no export writes",
    )
    parser.add_argument(
        "--max-age-seconds",
        type=float,
        default=7200,
        help="Maximum scheduled-export age (default: two hours)",
    )
    args = parser.parse_args()
    if args.check_schedule and (not args.checkpoint or args.archive_directory):
        parser.error("--check-schedule requires --checkpoint and forbids --archive-directory")
    database = os.environ.get("IDENTITY_DB", "").strip()
    if not database:
        parser.error("IDENTITY_DB must be configured")
    try:
        scheduled = None
        if args.check_schedule:
            directory = os.environ.get("AUDIT_CHECKPOINT_DIRECTORY", "").strip()
            if not directory:
                print("Scheduled checkpoint export is not configured.", file=sys.stderr)
                return 1
            try:
                scheduled, age = latest_checkpoint(
                    Path(directory), max_age_seconds=args.max_age_seconds
                )
            except ValueError as exc:
                print(f"Scheduled checkpoint check failed: {exc}", file=sys.stderr)
                return 1
        checkpoint = json.loads(args.checkpoint.read_text()) if args.checkpoint else None
        if checkpoint is not None and not isinstance(checkpoint, dict):
            raise ValueError("Checkpoint must be an object")
        with MongoClient(
            mongo_uri(os.environ, "identity"), serverSelectionTimeoutMS=10000
        ) as client:
            configuration = {
                "DB_COLLECTIONS_CONFIG": {"identity": load_collection_section("identity")}
            }
            result = verify_chain(
                client[database][get_audit_events_collection_name(configuration)],
                checkpoint=checkpoint,
            )
            if scheduled is not None:
                current = verify_chain(
                    client[database][get_audit_events_collection_name(configuration)],
                    checkpoint=scheduled,
                )
                result["scheduled_export"] = {"valid": current["valid"], "age_seconds": age}
                result["valid"] = result["valid"] and current["valid"]
                result["independent_checkpoint_supplied"] = True
            if args.archive_directory and result["valid"]:
                archive_checkpoint(result, args.archive_directory)
    except (OSError, ValueError, PyMongoError) as exc:
        print(
            f"Audit verification failed ({type(exc).__name__}). Check configuration and database availability.",
            file=sys.stderr,
        )
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
