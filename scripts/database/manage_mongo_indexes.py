#!/usr/bin/env python3
"""Inspect, apply, or explicitly retire Coyote3 MongoDB indexes."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.config import app_config  # noqa: E402
from api.infra.mongo.index_management import (  # noqa: E402
    build_index_plan,
    known_retired_indexes,
    retire_index,
)
from api.infra.mongo.runtime_adapter import MongoAdapter  # noqa: E402
from api.infra.security.indexes import ensure_security_indexes  # noqa: E402


def _config() -> object:
    """Select application configuration from the normalized ``ENV_NAME`` variable.

    Returns:
        Test, stage, or production configuration for recognized aliases;
        development configuration for an absent or unrecognized environment.
    """
    env = os.getenv("ENV_NAME", "development").strip().lower()
    if env in {"test", "testing"}:
        return app_config.TestConfig()
    if env in {"stage", "staging"}:
        return app_config.StageConfig()
    if env in {"prod", "production"}:
        return app_config.ProductionConfig()
    return app_config.DevelopmentConfig()


def _adapter(scope: str = "application") -> MongoAdapter:
    """Connect and initialize MongoDB repositories without ensuring their indexes.

    Args:
        scope: application excludes knowledgebases; knowledgebase selects only their repositories;
            all selects both. Only selected endpoints are pinged.

    Returns:
        Configured, pinged MongoAdapter using the environment-selected configuration.

    Raises:
        ValueError: MongoDB endpoint or numeric connection settings are invalid.
        pymongo.errors.PyMongoError: Client configuration or the connectivity check fails.

    Notes:
        This helper does not close the adapter or create repository indexes.
    """
    config_obj = _config()
    config = {name: getattr(config_obj, name) for name in dir(config_obj) if name.isupper()}
    app = SimpleNamespace(config=config, logger=logging.getLogger("coyote.mongo_indexes"))
    adapter = MongoAdapter()
    adapter.connect(app)
    adapter.setup()
    adapter._setup_repositories(ensure_indexes=False)
    repositories = list(adapter.iter_repositories())
    adapter.iter_repositories = lambda: iter(
        (name, repository)
        for name, repository in repositories
        if scope == "all"
        or (
            (repository.get_collection().database == adapter.knowledgebase_db)
            == (scope == "knowledgebase")
        )
    )
    databases = (
        [adapter.knowledgebase_db]
        if scope == "knowledgebase"
        else [adapter.coyote_db, adapter.identity_db, adapter.bam_db]
    )
    if scope == "all":
        databases.append(adapter.knowledgebase_db)
    for database in databases:
        database.client.admin.command("ping")
    return adapter


def _parser() -> argparse.ArgumentParser:
    """Define index inspection, application, and explicitly confirmed retirement commands.

    Returns:
        Parser requiring one subcommand; retirement requires collection, index,
        and confirmation names and optionally accepts a repository discriminator.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show contract state and known obsolete indexes")
    sub.add_parser("plan", help="Show only missing/conflicting contract entries")
    apply = sub.add_parser("apply", help="Create missing compatible indexes; never drops indexes")
    apply.add_argument("--summary", action="store_true", help="Print counts instead of full JSON")
    retire = sub.add_parser("retire", help="Drop one exact index during a maintenance window")
    retire.add_argument("--collection", required=True)
    retire.add_argument("--repository", help="Disambiguate equal collection names across services")
    retire.add_argument("--index", required=True)
    retire.add_argument("--confirm-index-name", required=True)
    for command in sub.choices.values():
        command.add_argument(
            "--scope",
            choices=("application", "knowledgebase", "all"),
            default="application",
            help="Index ownership; default: application",
        )
    return parser


def main() -> int:
    """Execute the selected index command and print the resulting contract state as JSON.

    Returns:
        Zero after printing index state and known retired indexes still present.
        The plan command omits entries already present. Apply with ``--summary``
        prints state counts and returns one if any required index remains unavailable.

    Raises:
        SystemExit: CLI parsing exits or the retirement confirmation differs from the index.
        ValueError: Retirement targets an unknown or ambiguous collection, a missing
            index, or the protected ``_id_`` index.
        pymongo.errors.PyMongoError: Index inspection or modification fails.

    Notes:
        Apply ensures repository and security indexes; retire drops the selected
        index. Status and plan do not request index creation or retirement.
    """
    args = _parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    adapter = _adapter(args.scope)
    if args.command == "apply":
        adapter.ensure_repository_indexes()
        if args.scope != "knowledgebase":
            ensure_security_indexes(
                primary_db=adapter.coyote_db,
                identity_db=adapter.identity_db,
                config=adapter.app.config,
                logger=adapter.app.logger,
            )
    elif args.command == "retire":
        if args.confirm_index_name != args.index:
            raise SystemExit("--confirm-index-name must exactly match --index")
        retire_index(
            adapter,
            collection_name=args.collection,
            index_name=args.index,
            repository_name=args.repository,
        )
    plan = build_index_plan(adapter, include_security=args.scope != "knowledgebase")
    if args.command == "apply" and args.summary:
        for state in ("present", "missing", "conflict"):
            print(f"[indexes] {state}={sum(item['state'] == state for item in plan)}")
        return 1 if any(item["state"] != "present" for item in plan) else 0
    if args.command == "plan":
        plan = [item for item in plan if item["state"] != "present"]
    print(
        json.dumps(
            {"indexes": plan, "retired_indexes_present": known_retired_indexes(adapter)},
            indent=2,
            default=str,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
