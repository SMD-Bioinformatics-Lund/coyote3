#!/usr/bin/env python3
"""Synchronize bundled permission policies and built-in role grants with MongoDB."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pymongo import MongoClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from api.config.loaders.collections import load_collection_mapping  # noqa: E402
from api.contracts.schemas.registry import normalize_collection_document  # noqa: E402

DEFAULT_SEED_DATA_DIR = ROOT_DIR / "api" / "config" / "bootstrap" / "rbac"


def _load_ndjson(path: Path) -> list[dict[str, Any]]:
    """Load object-per-line JSON from a bundled catalog file."""
    documents: list[dict[str, Any]] = []
    with path.open("rt", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise ValueError(f"Expected an object at {path}:{line_number}")
            documents.append(value)
    return documents


def synchronize_rbac_catalog(
    database: Any,
    *,
    permissions_collection: str,
    roles_collection: str,
    permission_docs: list[dict[str, Any]],
    role_docs: list[dict[str, Any]],
    actor: str = "sync_rbac_catalog",
) -> dict[str, int]:
    """Union bundled policies and roles into the existing database catalog."""
    now = datetime.now(timezone.utc)
    inserted_permissions = 0
    locked_permissions = 0
    inserted_roles = 0
    updated_roles = 0

    permissions = database[permissions_collection]
    for source in permission_docs:
        permission_id = str(source.get("permission_id") or "").strip().lower()
        if not permission_id:
            raise ValueError("Permission seed entry is missing permission_id")
        existing = permissions.find_one(
            {"permission_id": permission_id},
            {"_id": 1, "system_managed": 1, "is_active": 1},
        )
        if existing is not None:
            if not bool(existing.get("system_managed", False)) or not bool(
                existing.get("is_active", True)
            ):
                result = permissions.update_one(
                    {"_id": existing["_id"]},
                    {
                        "$set": {
                            "system_managed": True,
                            "is_active": True,
                            "updated_by": actor,
                            "updated_on": now,
                        }
                    },
                )
                locked_permissions += int(result.modified_count or 0)
            continue
        document = normalize_collection_document(
            "permissions",
            {
                **source,
                "permission_id": permission_id,
                "system_managed": True,
                "created_by": actor,
                "created_on": now,
                "updated_by": actor,
                "updated_on": now,
            },
        )
        permissions.insert_one(document)
        inserted_permissions += 1

    roles = database[roles_collection]
    for source in role_docs:
        role_id = str(source.get("role_id") or "").strip().lower()
        grants = sorted(
            {
                str(permission).strip().lower()
                for permission in source.get("permissions", [])
                if str(permission).strip()
            }
        )
        if not role_id or not grants:
            continue
        existing_role = roles.find_one({"role_id": role_id}, {"permissions": 1})
        if not existing_role:
            document = normalize_collection_document(
                "roles",
                {
                    **source,
                    "role_id": role_id,
                    "permissions": grants,
                    "created_by": actor,
                    "created_on": now,
                    "updated_by": actor,
                    "updated_on": now,
                },
            )
            roles.insert_one(document)
            inserted_roles += 1
            continue
        existing_grants = {
            str(permission).strip().lower()
            for permission in existing_role.get("permissions", [])
            if str(permission).strip()
        }
        missing_grants = sorted(set(grants) - existing_grants)
        if not missing_grants:
            continue
        result = roles.update_one(
            {"role_id": role_id},
            {
                "$addToSet": {"permissions": {"$each": missing_grants}},
                "$set": {"updated_by": actor, "updated_on": now},
            },
            upsert=False,
        )
        if result.modified_count:
            updated_roles += 1

    return {
        "inserted_permissions": inserted_permissions,
        "locked_permissions": locked_permissions,
        "inserted_roles": inserted_roles,
        "updated_roles": updated_roles,
    }


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description=(
            "Union bundled permission policies and roles into MongoDB. Existing policies, "
            "custom roles, role metadata, and extra grants are preserved."
        )
    )
    parser.add_argument("--mongo-uri", default=os.getenv("MONGO_URI", ""))
    parser.add_argument("--db", default=os.getenv("COYOTE3_DB", ""))
    parser.add_argument("--bam-db", default=os.getenv("BAM_DB", "BAM_Service"))
    parser.add_argument("--seed-data-dir", default=str(DEFAULT_SEED_DATA_DIR))
    return parser.parse_args()


def main() -> int:
    """Run the RBAC catalog synchronization command."""
    args = parse_args()
    if not args.mongo_uri or not args.db:
        raise SystemExit("--mongo-uri/MONGO_URI and --db/COYOTE3_DB are required")

    seed_dir = Path(args.seed_data_dir).expanduser().resolve()
    permission_docs = _load_ndjson(seed_dir / "permissions.seed.ndjson")
    role_docs = _load_ndjson(seed_dir / "roles.seed.ndjson")
    mapping = load_collection_mapping(primary_database=args.db, bam_database=args.bam_db)
    primary_mapping = mapping[args.db]

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    client.admin.command("ping")
    result = synchronize_rbac_catalog(
        client[args.db],
        permissions_collection=primary_mapping["permissions_collection"],
        roles_collection=primary_mapping["roles_collection"],
        permission_docs=permission_docs,
        role_docs=role_docs,
    )
    print(
        "[ok] RBAC catalog synchronized: "
        f"inserted_permissions={result['inserted_permissions']} "
        f"locked_permissions={result['locked_permissions']} "
        f"inserted_roles={result['inserted_roles']} "
        f"updated_roles={result['updated_roles']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
