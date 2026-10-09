#!/usr/bin/env python3
"""Install missing query-policy scopes without replacing center-authored versions."""

import argparse
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pymongo import MongoClient  # noqa: E402

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.mongo import configured_mongo_uri  # noqa: E402
from api.infra.mongo.repositories.audit_outbox import enqueue_audit  # noqa: E402
from api.infra.mongo.repositories.query_rule_revisions import (  # noqa: E402
    QueryRuleRevisionRepository,
    build_query_revision,
)
from api.infra.mongo.repositories.query_rules import QueryRuleRepository  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402
from scripts.bootstrap.query_rule_seed import prepare_query_rule_seeds  # noqa: E402


def install(db, *, actor: str, apply: bool = False) -> dict:
    """Plan or atomically insert missing installed rule scopes.

    Args:
        db: Explicitly selected application database; no database names are inferred.
        actor: Operator recorded as installer, not as an independent clinical reviewer.
        apply: False validates and reports only; True creates indexes and inserts records.

    Returns:
        Counts of missing and preserved scopes. Existing scopes, including retired
        versions, are never overwritten or republished.

    Raises:
        ValueError: Installation input is invalid or a scope changed after planning.
        PyMongoError: Index creation, transaction or audit persistence fails.
    """
    if not actor.strip():
        raise ValueError("Installer account must not be blank")
    mapping = load_collection_section("primary")
    catalog_path = ROOT / "api/config/bootstrap/reference/query_rule_sets.seed.ndjson"
    catalog = [json.loads(line) for line in catalog_path.read_text().splitlines() if line.strip()]
    documents = prepare_query_rule_seeds(
        catalog,
        list(db[mapping["assay_groups_collection"]].find()),
        actor=actor.strip(),
    )
    collection = db[mapping["query_rule_sets_collection"]]
    existing = set(collection.distinct("scope_key"))
    missing = [doc for doc in documents if doc["scope_key"] not in existing]
    revisions = db[mapping["query_rule_revisions_collection"]]
    baselines = [
        doc for doc in collection.find() if not revisions.find_one({"rule_oid": str(doc["_id"])})
    ]
    if apply:
        adapter = SimpleNamespace(
            query_rule_sets_collection=collection,
            query_rule_revisions_collection=db[mapping["query_rule_revisions_collection"]],
        )
        QueryRuleRepository(adapter).ensure_indexes()
        QueryRuleRevisionRepository(adapter).ensure_indexes()
        if missing:

            def write(session):
                """Commit new scopes and the installation audit receipt together."""
                if collection.find_one(
                    {"scope_key": {"$in": [doc["scope_key"] for doc in missing]}}, session=session
                ):
                    raise ValueError("A query-rule scope changed after planning; rerun the plan")
                collection.insert_many(missing, session=session)
                adapter.query_rule_revisions_collection.insert_many(
                    [build_query_revision(doc, "installed") for doc in missing], session=session
                )
                enqueue_audit(
                    db,
                    session,
                    event_type="query_rules.installed",
                    resource_type="query_rule",
                    resource_id="installation",
                    actor=actor.strip(),
                    metadata={"scopes": len(missing)},
                )

            run_transaction(db.client, write)
        if baselines:

            def capture(session):
                """Record retained versions as migration baselines without inventing history."""
                for planned in baselines:
                    current = collection.find_one(
                        {"_id": planned["_id"], "revision": planned["revision"]}, session=session
                    )
                    if current is None:
                        raise ValueError("Query rule changed during baseline capture; retry")
                    if not revisions.find_one({"rule_oid": str(current["_id"])}, session=session):
                        revisions.insert_one(
                            build_query_revision(current, "baseline_captured"), session=session
                        )
                enqueue_audit(
                    db,
                    session,
                    event_type="query_rules.baselines_captured",
                    resource_type="query_rule",
                    resource_id="installation",
                    actor=actor,
                    metadata={"versions": len(baselines)},
                )

            run_transaction(db.client, capture)
    return {
        "missing_scopes": len(missing),
        "preserved_scopes": len(documents) - len(missing),
        "planned_rules": [
            {"scope_key": doc["scope_key"], "content": doc["content"]} for doc in missing
        ],
        "preserved_scope_keys": sorted(
            doc["scope_key"] for doc in documents if doc["scope_key"] in existing
        ),
        "applied": apply,
        "revision_baselines": len(baselines),
    }


def main() -> int:
    """Read explicit deployment settings and dry-run unless --apply is supplied."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=configured_mongo_uri(os.environ, "primary"))
    parser.add_argument(
        "--db", default=os.getenv("COYOTE3_DB"), required=not os.getenv("COYOTE3_DB")
    )
    parser.add_argument("--actor", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    with MongoClient(args.mongo_uri) as client:
        print(
            json.dumps(
                install(
                    client[args.db],
                    actor=args.actor,
                    apply=args.apply,
                )
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
