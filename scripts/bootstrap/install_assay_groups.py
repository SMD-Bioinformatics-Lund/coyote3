#!/usr/bin/env python3
"""Install missing system and existing assay groups without rewriting scope references."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pymongo import MongoClient  # noqa: E402

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.mongo import configured_mongo_uri  # noqa: E402
from api.contracts.schemas.assay_groups import AssayGroupDoc  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402


def install(db, *, actor: str, apply: bool = False) -> int:
    """Plan or insert missing groups, preserving existing documents and clinical scopes.

    Args:
        db: Operational database selected by the operator.
        actor: Operator recorded on discovered center-owned groups.
        apply: Write only when true; otherwise validate and count missing definitions.

    Returns:
        Number of missing definitions in the plan.

    Raises:
        ValueError: An existing scope is not canonical and requires operator review.
    """
    mapping = load_collection_section("primary")
    collection = db[mapping["assay_groups_collection"]]
    seed_path = ROOT / "api/config/bootstrap/reference/assay_groups.seed.ndjson"
    seeds = [json.loads(line) for line in seed_path.read_text().splitlines() if line.strip()]
    planned = {item["group_id"]: item for item in seeds}
    for key, field in (
        ("asp_collection", "asp_group"),
        ("aspc_collection", "asp_group"),
        ("insilico_genelist_collection", "asp_groups"),
    ):
        for identifier in db[mapping[key]].distinct(field):
            if not identifier:
                continue
            candidate = AssayGroupDoc(
                group_id=identifier,
                display_name=identifier,
                created_by=actor,
                created_on=datetime.now(timezone.utc),
                system_managed=False,
            )
            if candidate.group_id != identifier:
                raise ValueError(
                    "Existing group identifiers require review; no scopes were renamed"
                )
            planned.setdefault(identifier, candidate.model_dump(exclude={"id_"}))
    documents = [
        AssayGroupDoc.model_validate(d).model_dump(exclude={"id_"}) for d in planned.values()
    ]
    existing = set(collection.distinct("group_id"))
    missing = [d for d in documents if d["group_id"] not in existing]
    if apply:
        collection.create_index([("group_id", 1)], unique=True, name="assay_group_id_unique")

        def write(session):
            """Insert definitions without replacing any installed record."""
            for field, default in (("is_active", True), ("version", 1)):
                collection.update_many(
                    {field: {"$exists": False}},
                    {"$set": {field: default}},
                    session=session,
                )
            for document in missing:
                collection.update_one(
                    {"group_id": document["group_id"]},
                    {"$setOnInsert": document},
                    upsert=True,
                    session=session,
                )

        run_transaction(db.client, write)
    return len(missing)


def main() -> int:
    """Read the operator-selected connection and execute a dry run unless --apply is supplied."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=configured_mongo_uri(os.environ, "primary"))
    parser.add_argument(
        "--db", default=os.getenv("COYOTE3_DB"), required=not os.getenv("COYOTE3_DB")
    )
    parser.add_argument("--actor", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not args.actor.strip():
        parser.error("--actor must not be blank")
    with MongoClient(args.mongo_uri) as client:
        count = install(client[args.db], actor=args.actor.strip(), apply=args.apply)
    print(f"{'Installed' if args.apply else 'Would install'} {count} missing assay groups")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
