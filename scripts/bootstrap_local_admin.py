#!/usr/bin/env python3
"""Create or update initial local bootstrap user/role/permission in Mongo."""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pymongo import MongoClient  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from api.contracts.schemas.registry import normalize_collection_document  # noqa: E402

DEFAULT_SEED_DATA_DIR = ROOT_DIR / "tests" / "data" / "seed_data"


def _normalize_permission_id(permission_id) -> str:
    """Normalize a permission identifier for bootstrap upserts."""
    return str(permission_id or "").strip().lower()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap initial local API user (one-time setup)."
    )
    parser.add_argument(
        "--mongo-uri", required=True, help="Mongo URI with readWrite access to app DB"
    )
    parser.add_argument("--db", default="coyote3", help="Application DB name")
    parser.add_argument("--username", required=True, help="Bootstrap username (login identifier)")
    parser.add_argument("--email", required=True, help="Bootstrap email address")
    parser.add_argument("--password", required=True, help="Bootstrap password (plain text input)")
    parser.add_argument("--role-id", default="superuser", help="Role id to assign")
    parser.add_argument(
        "--seed-data-dir",
        default=str(DEFAULT_SEED_DATA_DIR),
        help="Directory containing compressed RBAC seed files",
    )
    parser.add_argument("--assay-group", default="hematology", help="Initial assay group")
    parser.add_argument("--assay", default="assay_1", help="Initial assay id")
    return parser.parse_args()


def _fail_if_placeholder_values(args: argparse.Namespace) -> None:
    """Abort when placeholder values are still present in CLI inputs."""
    flagged: list[str] = []
    for key, value in vars(args).items():
        if not isinstance(value, str):
            continue
        if "change_me" in value.lower():
            flagged.append(key)

    if flagged:
        joined = ", ".join(sorted(flagged))
        print(
            f"[error] Refusing bootstrap because placeholder values were detected in: {joined}. "
            "Replace all CHANGE_ME values and retry.",
            file=sys.stderr,
        )
        raise SystemExit(2)


def _load_seed_ndjson_gz(path: Path) -> list[dict]:
    docs: list[dict] = []
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            value = json.loads(text)
            if not isinstance(value, dict):
                raise SystemExit(f"Seed file must contain JSON objects per line: {path}")
            docs.append(value)
    return docs


def _load_bootstrap_rbac(seed_data_dir: Path) -> tuple[list[dict], list[dict]]:
    permissions_path = seed_data_dir / "permissions.seed.ndjson.gz"
    roles_path = seed_data_dir / "roles.seed.ndjson.gz"
    if not permissions_path.exists():
        raise SystemExit(f"Missing bootstrap permission seed file: {permissions_path}")
    if not roles_path.exists():
        raise SystemExit(f"Missing bootstrap role seed file: {roles_path}")
    permissions = _load_seed_ndjson_gz(permissions_path)
    roles = _load_seed_ndjson_gz(roles_path)
    if not permissions:
        raise SystemExit(f"Bootstrap permission seed file is empty: {permissions_path}")
    if not roles:
        raise SystemExit(f"Bootstrap role seed file is empty: {roles_path}")
    return permissions, roles


def _upsert_permission(db, permission_doc: dict) -> None:
    permission_id = str(permission_doc.get("permission_id") or "").strip()
    canonical_id = _normalize_permission_id(permission_id)
    if not canonical_id:
        raise SystemExit("Permission seed entry is missing permission_id")
    doc = normalize_collection_document(
        "permissions",
        {
            **permission_doc,
            "permission_id": canonical_id,
            "permission_name": _normalize_permission_id(permission_doc.get("permission_name"))
            or canonical_id,
        },
    )
    db["permissions"].update_one(
        {"permission_id": canonical_id},
        {"$set": doc},
        upsert=True,
    )


def _upsert_role(db, role_doc: dict) -> None:
    role_id = str(role_doc.get("role_id") or "").strip().lower()
    if not role_id:
        raise SystemExit("Role seed entry is missing role_id")
    doc = normalize_collection_document(
        "roles",
        {
            **role_doc,
            "role_id": role_id,
        },
    )
    db["roles"].update_one(
        {"role_id": role_id},
        {"$set": doc},
        upsert=True,
    )


def _upsert_user(
    db,
    *,
    username: str,
    email: str,
    password: str,
    role_id: str,
    assay_group: str,
    assay: str,
) -> None:
    username = username.strip().lower()
    email = email.strip().lower()
    fullname = " ".join(part.capitalize() for part in username.split(".")) or username
    actor = "bootstrap_local_admin"
    now_utc = datetime.now(timezone.utc)
    user_doc = normalize_collection_document(
        "users",
        {
            "email": email.strip().lower(),
            "username": username,
            "fullname": fullname,
            "firstname": fullname.split(" ")[0],
            "lastname": " ".join(fullname.split(" ")[1:]) if len(fullname.split(" ")) > 1 else "",
            "job_title": "Center Bootstrap User",
            "auth_type": "coyote3",
            "password": generate_password_hash(password, method="pbkdf2:sha256"),
            "roles": [role_id],
            "is_active": True,
            "permissions": [],
            "deny_permissions": [],
            "must_change_password": True,
            "environments": ["production", "development", "testing", "validation"],
            "assay_groups": [assay_group],
            "assays": [assay],
            "created_by": actor,
            "created_on": now_utc,
            "updated_by": actor,
            "updated_on": now_utc,
        },
    )
    db["users"].update_one(
        {"username": username},
        {"$set": user_doc},
        upsert=True,
    )


def _superuser_exists(db) -> bool:
    return db["users"].count_documents({"roles": "superuser"}, limit=1) > 0


def main() -> int:
    args = parse_args()
    _fail_if_placeholder_values(args)
    args.role_id = str(args.role_id).strip().lower()
    args.assay_group = str(args.assay_group).strip().lower()
    args.assay = str(args.assay).strip().lower()
    seed_data_dir = Path(str(args.seed_data_dir)).expanduser().resolve()
    permission_docs, role_docs = _load_bootstrap_rbac(seed_data_dir)
    role_map = {
        str(doc.get("role_id") or "").strip().lower(): doc
        for doc in role_docs
        if isinstance(doc, dict)
    }
    if args.role_id not in role_map:
        available_roles = ", ".join(sorted(role for role in role_map if role))
        raise SystemExit(
            f"Role '{args.role_id}' not found in {seed_data_dir / 'roles.seed.ndjson.gz'}. "
            f"Available roles: {available_roles}"
        )
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    client.admin.command("ping")
    db = client[args.db]

    if args.role_id == "superuser" and _superuser_exists(db):
        raise SystemExit(
            "A superuser already exists. bootstrap_local_admin.py may create only the first "
            "bootstrap superuser. Additional superusers must be created by an existing superuser."
        )

    for permission_doc in permission_docs:
        _upsert_permission(db, permission_doc)

    for role_doc in role_docs:
        _upsert_role(db, role_doc)

    _upsert_user(
        db,
        username=args.username,
        email=args.email,
        password=args.password,
        role_id=args.role_id,
        assay_group=args.assay_group,
        assay=args.assay,
    )

    print(
        f"[ok] local bootstrap user ready: username={args.username} email={args.email} role={args.role_id} "
        f"assay_group={args.assay_group} assay={args.assay}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
