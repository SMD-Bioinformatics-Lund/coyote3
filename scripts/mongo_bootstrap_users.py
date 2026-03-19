#!/usr/bin/env python3
"""Create or rotate MongoDB app users for environment databases."""

from __future__ import annotations

import argparse

from pymongo import MongoClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create/update a readWrite Mongo app user in a target database."
    )
    parser.add_argument("--mongo-uri", required=True, help="Admin-capable Mongo URI")
    parser.add_argument("--app-db", required=True, help="Application database name")
    parser.add_argument("--app-user", required=True, help="Application username")
    parser.add_argument("--app-password", required=True, help="Application password")
    parser.add_argument(
        "--roles",
        default="readWrite",
        help="Comma-separated roles granted on --app-db (default: readWrite)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roles = [
        {"role": role.strip(), "db": args.app_db} for role in args.roles.split(",") if role.strip()
    ]
    if not roles:
        raise SystemExit("At least one role is required")

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    client.admin.command("ping")
    app_db = client[args.app_db]

    existing = app_db.command("usersInfo", args.app_user).get("users", [])
    if existing:
        app_db.command("updateUser", args.app_user, pwd=args.app_password, roles=roles)
        print(f"updated user '{args.app_user}' in db '{args.app_db}'")
    else:
        app_db.command("createUser", args.app_user, pwd=args.app_password, roles=roles)
        print(f"created user '{args.app_user}' in db '{args.app_db}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
