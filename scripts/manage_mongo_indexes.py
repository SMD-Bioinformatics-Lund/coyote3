#!/usr/bin/env python3
"""Inspect, apply, or explicitly retire Coyote3 MongoDB indexes."""

from __future__ import annotations

import argparse
import json
import logging
import os
from types import SimpleNamespace

from api.config import app_config
from api.infra.mongo.index_management import build_index_plan, known_retired_indexes, retire_index
from api.infra.mongo.runtime_adapter import MongoAdapter
from api.infra.security.indexes import ensure_security_indexes


def _config() -> object:
    env = os.getenv("ENV_NAME", "development").strip().lower()
    if env in {"test", "testing"}:
        return app_config.TestConfig()
    if env in {"stage", "staging"}:
        return app_config.StageConfig()
    if env in {"prod", "production"}:
        return app_config.ProductionConfig()
    return app_config.DevelopmentConfig()


def _adapter() -> MongoAdapter:
    config_obj = _config()
    config = {name: getattr(config_obj, name) for name in dir(config_obj) if name.isupper()}
    app = SimpleNamespace(config=config, logger=logging.getLogger("coyote.mongo_indexes"))
    adapter = MongoAdapter()
    adapter.app = app
    adapter.client = adapter._get_mongoclient(config["MONGO_URI"])
    adapter._setup_dbs(adapter.client)
    adapter.setup()
    adapter._setup_repositories(ensure_indexes=False)
    adapter.client.admin.command("ping")
    return adapter


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Show contract state and known obsolete indexes")
    sub.add_parser("plan", help="Show only missing/conflicting contract entries")
    sub.add_parser("apply", help="Create missing compatible indexes; never drops indexes")
    retire = sub.add_parser("retire", help="Drop one exact index during a maintenance window")
    retire.add_argument("--collection", required=True)
    retire.add_argument("--index", required=True)
    retire.add_argument("--confirm-index-name", required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    adapter = _adapter()
    if args.command == "apply":
        adapter.ensure_repository_indexes()
        ensure_security_indexes(
            primary_db=adapter.coyote_db,
            identity_db=adapter.identity_db,
            config=adapter.app.config,
            logger=adapter.app.logger,
        )
    elif args.command == "retire":
        if args.confirm_index_name != args.index:
            raise SystemExit("--confirm-index-name must exactly match --index")
        retire_index(adapter, collection_name=args.collection, index_name=args.index)
    plan = build_index_plan(adapter)
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
