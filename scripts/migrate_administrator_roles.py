#!/usr/bin/env python3
"""Install administrator responsibility boundaries with an explicitly selected system owner."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.mongo import configured_mongo_uri  # noqa: E402
from api.infra.mongo.transactions import run_transaction  # noqa: E402


def migrate(database, *, username: str, apply: bool = False) -> dict[str, str]:
    """Assign a named system administrator before replacing bundled admin grants.

    Args:
        database: Explicit identity database.
        username: Existing active, non-superuser account selected by the operator.
        apply: Commit only when True; otherwise validate and report the plan.

    Returns:
        Operation mode and the affected bundled role identifiers; no account details.

    Raises:
        ValueError: The selected account is absent, inactive, or the emergency superuser.

    Notes:
        Account membership and role replacement commit together. Custom roles,
        passwords, installed-account flags, and other users are not changed.
    """
    mapping = load_collection_section("identity")
    users = database[mapping["users_collection"]]
    roles = database[mapping["roles_collection"]]
    username = username.strip().lower()
    definitions = [
        json.loads(line)
        for line in (ROOT / "api/config/bootstrap/rbac/roles.seed.ndjson").read_text().splitlines()
        if line.strip()
    ]

    def operation(session):
        """Recheck the chosen account and atomically install the responsibility split."""
        account = users.find_one({"username": username, "is_active": True}, session=session)
        if not account or "superuser" in account.get("roles", []):
            raise ValueError(
                "Select an existing active account distinct from the emergency superuser"
            )
        if not apply:
            return
        now = datetime.now(timezone.utc)
        users.update_one(
            {"_id": account["_id"]},
            {
                "$addToSet": {"roles": "sys_admin"},
                "$set": {"updated_on": now, "updated_by": "administrator_role_migration"},
            },
            session=session,
        )
        for definition in definitions:
            if definition["role_id"] not in {"admin", "sys_admin"}:
                continue
            roles.update_one(
                {"role_id": definition["role_id"]},
                {
                    "$set": {
                        **definition,
                        "updated_on": now,
                        "updated_by": "administrator_role_migration",
                    }
                },
                upsert=True,
                session=session,
            )

    if apply:
        run_transaction(database.client, operation)
    else:
        operation(None)
    return {"status": "applied" if apply else "dry-run", "roles": "admin,sys_admin"}


def main() -> int:
    """Run a reviewed responsibility migration against the configured identity database."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--system-admin-user", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    uri = configured_mongo_uri(os.environ, "identity")
    name = os.getenv("IDENTITY_DB", "")
    if not uri or not name:
        parser.error("IDENTITY_MONGO_URI and IDENTITY_DB must be configured")
    with MongoClient(uri, serverSelectionTimeoutMS=7000) as client:
        print(migrate(client[name], username=args.system_admin_user, apply=args.apply))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
