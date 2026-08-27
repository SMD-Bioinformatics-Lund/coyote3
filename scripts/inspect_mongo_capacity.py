#!/usr/bin/env python3
"""Emit a read-only MongoDB collection-capacity snapshot for a maintenance record."""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from api.config import app_config
from api.infra.mongo.runtime_adapter import MongoAdapter


def runtime_config() -> object:
    """Return the application configuration selected by ``ENV_NAME``."""
    environment = os.getenv("ENV_NAME", "development").strip().lower()
    if environment in {"test", "testing"}:
        return app_config.TestConfig()
    if environment in {"stage", "staging"}:
        return app_config.StageConfig()
    if environment in {"prod", "production"}:
        return app_config.ProductionConfig()
    return app_config.DevelopmentConfig()


def build_adapter() -> MongoAdapter:
    """Connect an adapter without creating, changing, or retiring indexes."""
    configuration = runtime_config()
    config = {name: getattr(configuration, name) for name in dir(configuration) if name.isupper()}
    app = SimpleNamespace(config=config, logger=logging.getLogger("coyote.mongo_capacity"))
    adapter = MongoAdapter()
    adapter.app = app
    adapter.client = adapter._get_mongoclient(config["MONGO_URI"])
    adapter._setup_dbs(adapter.client)
    adapter.setup()
    adapter._setup_repositories(ensure_indexes=False)
    adapter.client.admin.command("ping")
    return adapter


def collection_snapshot(collection: Any) -> dict[str, Any]:
    """Measure metadata for one collection without reading clinical documents."""
    started = time.perf_counter()
    result: dict[str, Any] = {"collection": collection.name}
    try:
        result["estimated_document_count"] = collection.estimated_document_count()
        result["count_duration_ms"] = round((time.perf_counter() - started) * 1000, 2)
    except Exception as error:  # pragma: no cover - exercised against restricted Mongo roles
        result["count_error"] = str(error)

    try:
        stats = collection.database.command("collStats", collection.name)
        result.update(
            {
                "storage_bytes": stats.get("storageSize"),
                "data_bytes": stats.get("size"),
                "index_bytes": stats.get("totalIndexSize"),
            }
        )
    except Exception as error:  # pragma: no cover - depends on deployed Mongo privileges
        result["stats_error"] = str(error)

    try:
        result["indexes"] = [index["name"] for index in collection.list_indexes()]
    except Exception as error:  # pragma: no cover - depends on deployed Mongo privileges
        result["indexes_error"] = str(error)
    return result


def snapshot(adapter: Any, requested_collections: set[str]) -> list[dict[str, Any]]:
    """Return deterministic snapshots for configured primary-database collections."""
    collections: dict[str, Any] = {}
    collection_mapping = adapter.app.config.get("DB_COLLECTIONS_CONFIG", {}).get(
        adapter.app.config["COYOTE3_DB"], {}
    )
    for collection_name in collection_mapping.values():
        collections[collection_name] = adapter.coyote_db[collection_name]

    # Repositories can expose an enabled plugin collection that is not present
    # in the static mapping. Include it while preserving the same read-only flow.
    for _repository_name, repository in adapter.iter_repositories():
        collection = repository.get_collection()
        collections[collection.name] = collection

    if requested_collections:
        collections = {
            collection_name: collection
            for collection_name, collection in collections.items()
            if collection_name in requested_collections
        }
    unknown = requested_collections.difference(collections)
    if unknown:
        raise ValueError(f"Unknown configured collection(s): {', '.join(sorted(unknown))}")
    return [collection_snapshot(collection) for _, collection in sorted(collections.items())]


def parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument(
        "--collection",
        action="append",
        default=[],
        help="Inspect one managed collection by its MongoDB collection name. Repeat as needed.",
    )
    command.add_argument("--output", help="Write the JSON snapshot to this file instead of stdout.")
    return command


def main() -> int:
    """Run the read-only capacity snapshot command."""
    args = parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    try:
        adapter = build_adapter()
        collections = snapshot(adapter, set(args.collection))
    except ValueError as error:
        parser().error(str(error))
    payload = {
        "environment": os.getenv("ENV_NAME", "development"),
        "database": adapter.get_db_name(),
        "generated_at": datetime.now(UTC).isoformat(),
        "collections": collections,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as output:
            output.write(f"{rendered}\n")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
