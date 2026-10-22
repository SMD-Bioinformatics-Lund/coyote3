#!/usr/bin/env python3
"""Verify clinical audit chains and optionally compare an independently retained checkpoint."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pymongo import MongoClient  # noqa: E402
from pymongo.errors import PyMongoError  # noqa: E402

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.mongo import mongo_uri  # noqa: E402
from api.config.security import get_audit_events_collection_name  # noqa: E402
from api.infra.mongo.repositories.audit_integrity import verify_chain  # noqa: E402


def main() -> int:
    """Read the configured identity database and print a credential-free verification result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--checkpoint", type=Path, help="Trusted JSON from an earlier successful verification"
    )
    args = parser.parse_args()
    database = os.environ.get("IDENTITY_DB", "").strip()
    if not database:
        parser.error("IDENTITY_DB must be configured")
    try:
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
