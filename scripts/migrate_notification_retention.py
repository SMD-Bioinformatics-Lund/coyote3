#!/usr/bin/env python3
"""Retain notification records while treating expiry as an inbox visibility deadline."""

import argparse
import os
import sys
from pathlib import Path

from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.mongo import configured_mongo_uri  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402


def migrate(collection, *, apply: bool = False) -> dict[str, int]:
    """Remove destructive expiry indexes and identify existing administrative broadcasts.

    Args:
        collection: Configured application's notification collection.
        apply: Write only when explicitly requested; otherwise return planned counts.

    Returns:
        Number of TTL indexes removed and existing broadcasts marked.

    Notes:
        Index DDL cannot run inside a MongoDB transaction. Stop API and workers for
        this migration. Existing expiry dates and message content are preserved.
        Records already removed by the old TTL index cannot be recovered here.
    """
    exists = collection.name in collection.database.list_collection_names()
    ttl = [
        index["name"]
        for index in (collection.list_indexes() if exists else [])
        if list(index["key"].items()) == [("expires_on", 1)] and "expireAfterSeconds" in index
    ]
    selector = {"source": "Administrative broadcast", "is_broadcast": {"$ne": True}}
    result = {"ttl_indexes": len(ttl), "broadcasts": collection.count_documents(selector)}
    if apply:
        for name in ttl:
            collection.drop_index(name)
        collection.create_index("expires_on", name="expires_on_1")
        run_transaction(
            collection.database.client,
            lambda session: collection.update_many(
                selector, {"$set": {"is_broadcast": True}}, session=session
            ),
        )
    return result


def main() -> int:
    """Run an explicit dry run or apply against the configured application database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    uri = configured_mongo_uri(os.environ, "primary")
    database = os.getenv("COYOTE3_DB", "")
    if not uri or not database:
        parser.error("COYOTE3_MONGO_URI and COYOTE3_DB must be configured")
    with MongoClient(uri, serverSelectionTimeoutMS=7000) as client:
        name = load_collection_section("primary")["notifications_collection"]
        print(migrate(client[database][name], apply=args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
