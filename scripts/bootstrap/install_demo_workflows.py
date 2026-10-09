#!/usr/bin/env python3
"""Plan or install synthetic workflow configuration in a local demo database.

Requires an initialized local replica set and application baseline. This command
never installs samples, findings, accounts or published report rules. Existing
fixture scopes are rejected rather than overwritten.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit

from pymongo import MongoClient

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from api.application.demo_installation import DemoInstallationService  # noqa: E402
from api.infra.mongo.repositories.demo_installation import DemoInstallationRepository  # noqa: E402


def validate_target(uri: str, database: str) -> None:
    """Require a loopback Mongo endpoint and an explicitly named demonstration database.

    Args:
        uri: A single-host MongoDB URI for the local test installation.
        database: Target name beginning with ``coyote3_demo``.

    Raises:
        ValueError: The target could be a remote or ordinary application database.
    """
    parsed = urlsplit(uri)
    if parsed.scheme != "mongodb" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("Only a loopback MongoDB endpoint is supported")
    if "," in parsed.netloc or parsed.path not in {"", "/"}:
        raise ValueError("Use one local endpoint with the database supplied through --db")
    if database != "coyote3_demo" and not database.startswith("coyote3_demo_"):
        raise ValueError("Database must be coyote3_demo or start with coyote3_demo_")


def main() -> None:
    """Validate the entire configuration, then optionally insert it in one transaction."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--actor", required=True, help="Existing demonstration administrator")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    validate_target(args.mongo_uri, args.db)
    if not args.actor.strip():
        raise ValueError("Actor must not be blank")
    with MongoClient(
        args.mongo_uri, directConnection=True, serverSelectionTimeoutMS=5000
    ) as client:
        repository = DemoInstallationRepository(client[args.db])
        service = DemoInstallationService(repository, ingest=None)
        documents = service.configuration(args.actor)
        repository.preflight(documents)
        print(json.dumps({name: len(rows) for name, rows in documents.items()}, indent=2))
        if not args.apply:
            print("Plan only; repeat with --apply to install this configuration")
            return
        repository.install(documents, args.actor)
        print("Installed synthetic configuration; report rules remain unpublished drafts")


if __name__ == "__main__":
    main()
