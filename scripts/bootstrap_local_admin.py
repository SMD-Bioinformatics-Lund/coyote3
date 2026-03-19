#!/usr/bin/env python3
"""Create or update initial local admin user/role/permission in Mongo."""

from __future__ import annotations

import argparse

from pymongo import MongoClient
from werkzeug.security import generate_password_hash


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap initial local API admin (one-time setup)."
    )
    parser.add_argument(
        "--mongo-uri", required=True, help="Mongo URI with readWrite access to app DB"
    )
    parser.add_argument("--db", default="coyote3", help="Application DB name")
    parser.add_argument("--email", required=True, help="Admin email/username")
    parser.add_argument("--password", required=True, help="Admin password (plain text input)")
    parser.add_argument("--role-id", default="admin", help="Role id to assign")
    parser.add_argument(
        "--permission-id",
        default="edit_sample",
        help="Permission id for sample updates (default: edit_sample)",
    )
    parser.add_argument("--assay-group", default="GROUP_A", help="Initial assay group")
    parser.add_argument("--assay", default="ASSAY_A", help="Initial assay id")
    return parser.parse_args()


def _upsert_permission(db, permission_id: str) -> None:
    db["permissions"].update_one(
        {"permission_id": permission_id},
        {
            "$setOnInsert": {
                "permission_name": permission_id,
                "category": "sample",
                "is_active": True,
            }
        },
        upsert=True,
    )


def _upsert_role(db, role_id: str, permission_id: str) -> None:
    db["roles"].update_one(
        {"role_id": role_id},
        {
            "$setOnInsert": {
                "name": "Administrator",
                "level": 100,
                "is_active": True,
                "permissions": [permission_id],
                "deny_permissions": [],
            }
        },
        upsert=True,
    )


def _upsert_user(
    db,
    *,
    email: str,
    password: str,
    role_id: str,
    assay_group: str,
    assay: str,
) -> None:
    username = email.strip().lower()
    fullname = " ".join(part.capitalize() for part in username.split("@")[0].split(".")) or username
    db["users"].update_one(
        {"email": username},
        {
            "$set": {
                "email": username,
                "username": username,
                "fullname": fullname,
                "firstname": fullname.split(" ")[0],
                "lastname": (
                    " ".join(fullname.split(" ")[1:]) if len(fullname.split(" ")) > 1 else ""
                ),
                "auth_type": "coyote3",
                "password": generate_password_hash(password, method="pbkdf2:sha256"),
                "role": role_id,
                "is_active": True,
                "permissions": [],
                "deny_permissions": [],
                "environments": ["production", "development", "test", "validation"],
                "assay_groups": [assay_group],
                "assays": [assay],
            }
        },
        upsert=True,
    )


def main() -> int:
    args = parse_args()
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    client.admin.command("ping")
    db = client[args.db]

    _upsert_permission(db, args.permission_id)
    _upsert_role(db, args.role_id, args.permission_id)
    _upsert_user(
        db,
        email=args.email,
        password=args.password,
        role_id=args.role_id,
        assay_group=args.assay_group,
        assay=args.assay,
    )

    print(
        f"[ok] local admin ready: email={args.email} role={args.role_id} "
        f"assay_group={args.assay_group} assay={args.assay}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
