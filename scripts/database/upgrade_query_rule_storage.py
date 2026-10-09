#!/usr/bin/env python3
"""Upgrade legacy query-rule identities and capture immutable revision baselines."""

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bson.json_util import dumps  # noqa: E402
from dotenv import dotenv_values  # noqa: E402
from pymongo import MongoClient  # noqa: E402

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.contracts.schemas.query_rules import QueryRuleDoc, QueryRuleScope  # noqa: E402
from api.infra.mongo.repositories.audit_outbox import enqueue_audit  # noqa: E402
from api.infra.mongo.repositories.query_rule_revisions import (  # noqa: E402
    QueryRuleRevisionRepository,
    build_query_revision,
)
from api.infra.mongo.repositories.query_rules import QueryRuleRepository  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402


def upgrade(db, *, actor: str, backup: Path | None = None, apply: bool = False) -> dict:
    """Plan or atomically upgrade query-rule storage without changing clinical content.

    Args:
        db: Explicit application database, never inferred from another service.
        actor: Operator recorded in the migration audit and new baselines.
        backup: New private Extended JSON file required when applying changes.
        apply: False validates and reports; True backs up and commits changes.

    Returns:
        Planned identity changes and baseline count, without credentials or rule content.

    Raises:
        ValueError: Scope identities collide, immutable legacy history exists, or input
            is incomplete. No versions are silently merged or renumbered.
        RuntimeError: A concurrent change invalidates the inspected migration plan.
    """
    if not actor.strip():
        raise ValueError("An operator is required")
    mapping = load_collection_section("primary")
    rules = db[mapping["query_rule_sets_collection"]]
    history = db[mapping["query_rule_revisions_collection"]]
    originals = list(rules.find())
    plans, versions, published = [], set(), set()
    now = datetime.now(timezone.utc)
    for original in originals:
        scope = QueryRuleScope.model_validate(original["scope"])
        key = scope.key()
        version_key = (key, original["version"])
        if version_key in versions or (original["status"] == "published" and key in published):
            raise ValueError(
                f"Normalized scope collision: {key}; resolve explicitly before migration"
            )
        versions.add(version_key)
        if original["status"] == "published":
            published.add(key)
        changed = (
            any(original.get(field) != key for field in ("scope_key", "query_id", "name"))
            or original["scope"].get("subpanel_id") == "base"
        )
        existing_history = history.find_one({"rule_oid": str(original["_id"])})
        if changed and existing_history:
            raise ValueError(
                "Legacy identity has immutable history; automatic rewriting is prohibited"
            )
        candidate = {
            **original,
            "scope": scope.model_dump(),
            "scope_key": key,
            "query_id": key,
            "name": key,
        }
        if changed:
            candidate.update(
                revision=original.get("revision", 1) + 1, updated_on=now, updated_by=actor
            )
        candidate = QueryRuleDoc.model_validate(candidate).model_dump(
            by_alias=True, exclude_none=True
        )
        if changed or not existing_history:
            plans.append((original, candidate, changed))
    if apply and plans:
        if backup is None:
            raise ValueError("--backup is required when applying changes")
        # Exclusive creation protects an earlier migration backup from overwrite.
        with os.fdopen(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            stream.write(
                dumps({"database": db.name, "rules": originals, "revisions": list(history.find())})
            )
        adapter = SimpleNamespace(
            query_rule_sets_collection=rules, query_rule_revisions_collection=history
        )
        QueryRuleRepository(adapter).ensure_indexes()
        QueryRuleRevisionRepository(adapter).ensure_indexes()

        def write(session):
            """Recheck inspected versions and atomically save rules, history and audit."""
            if rules.count_documents({}, session=session) != len(originals):
                raise RuntimeError("Query rules changed during migration; rerun the plan")
            for original, candidate, changed in plans:
                selector = {
                    "_id": original["_id"],
                    "revision": original.get("revision", 1),
                    "scope_key": original["scope_key"],
                }
                current = rules.find_one(selector, session=session)
                if current != original or history.find_one(
                    {"rule_oid": str(original["_id"])}, session=session
                ):
                    raise RuntimeError(
                        "Query rule or history changed during migration; rerun the plan"
                    )
                rules.replace_one(selector, candidate, session=session)
                history.insert_one(
                    build_query_revision(
                        candidate, "identity_migrated" if changed else "baseline_captured"
                    ),
                    session=session,
                )
            enqueue_audit(
                db,
                session,
                event_type="query_rules.storage_upgraded",
                actor=actor,
                resource_type="query_rule",
                resource_id="migration",
                metadata={"versions": len(plans), "backup": str(backup)},
            )

        run_transaction(db.client, write)
    return {
        "applied": apply,
        "versions": len(plans),
        "identities": [candidate["query_id"] for _, candidate, _ in plans],
    }


def main() -> None:
    """Require an explicit MongoDB target and default to a read-only migration plan."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", required=True)
    parser.add_argument("--db", required=True)
    parser.add_argument("--actor", required=True)
    parser.add_argument(
        "--env-file", type=Path, help="Deployment environment for transactional audit routing"
    )
    parser.add_argument("--backup", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if args.env_file:
        if not args.env_file.is_file():
            parser.error("Environment file does not exist")
        os.environ.update(
            {key: value for key, value in dotenv_values(args.env_file).items() if value is not None}
        )
    if args.apply:
        from api.infra.mongo.repositories.audit_outbox import audit_route

        audit_route(os.environ)
    with MongoClient(args.mongo_uri, serverSelectionTimeoutMS=5000) as client:
        print(
            dumps(upgrade(client[args.db], actor=args.actor, backup=args.backup, apply=args.apply))
        )


if __name__ == "__main__":
    main()
