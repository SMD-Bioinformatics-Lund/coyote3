#!/usr/bin/env python3
"""Create or update initial local admin user/role/permission in Mongo."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone

from pymongo import MongoClient
from werkzeug.security import generate_password_hash

from api.contracts.schemas.registry import normalize_collection_document

ROLE_PROFILES = {
    "external": {"name": "External", "level": 1, "color": "#64748B"},
    "viewer": {"name": "Viewer", "level": 5, "color": "#3B82F6"},
    "intern": {"name": "Intern", "level": 7, "color": "#8B5CF6"},
    "user": {"name": "User", "level": 9, "color": "#16A34A"},
    "manager": {"name": "Manager", "level": 99, "color": "#F59E0B"},
    "developer": {"name": "Developer", "level": 9999, "color": "#DC2626"},
    "admin": {"name": "Administrator", "level": 99999, "color": "#111827"},
}

BASE_PERMISSION_IDS = [
    "add_sample_comment",
    "add_variant_comment",
    "assign_tier",
    "create_asp",
    "create_aspc",
    "create_isgl",
    "create_permission_policy",
    "create_report",
    "create_role",
    "create_user",
    "delete_asp",
    "delete_aspc",
    "delete_isgl",
    "delete_permission_policy",
    "delete_role",
    "delete_sample_global",
    "delete_user",
    "download_cnvs",
    "download_snvs",
    "download_translocs",
    "edit_asp",
    "edit_aspc",
    "edit_isgl",
    "edit_permission_policy",
    "edit_role",
    "edit_sample",
    "edit_user",
    "hide_sample_comment",
    "hide_variant_comment",
    "manage_cnvs",
    "manage_snvs",
    "manage_translocs",
    "preview_report",
    "remove_tier",
    "unhide_sample_comment",
    "unhide_variant_comment",
    "view_asp",
    "view_aspc",
    "view_gene_annotations",
    "view_isgl",
    "view_permission_policy",
    "view_reports",
    "view_role",
    "view_sample_global",
    "view_user",
]

ROLE_BASE_PERMISSIONS = {
    "external": ["view_gene_annotations"],
    "viewer": [
        "view_gene_annotations",
        "view_asp",
        "view_aspc",
        "view_isgl",
        "view_reports",
        "download_snvs",
        "download_cnvs",
        "download_translocs",
        "preview_report",
    ],
    "intern": [
        "view_gene_annotations",
        "view_asp",
        "view_aspc",
        "view_isgl",
        "view_reports",
        "download_snvs",
        "download_cnvs",
        "download_translocs",
        "preview_report",
        "add_sample_comment",
        "add_variant_comment",
    ],
    "user": [
        "view_gene_annotations",
        "view_asp",
        "view_aspc",
        "view_isgl",
        "view_reports",
        "download_snvs",
        "download_cnvs",
        "download_translocs",
        "preview_report",
        "add_sample_comment",
        "add_variant_comment",
        "edit_sample",
        "manage_snvs",
        "manage_cnvs",
        "manage_translocs",
    ],
    "manager": [
        "view_gene_annotations",
        "view_asp",
        "view_aspc",
        "view_isgl",
        "view_reports",
        "download_snvs",
        "download_cnvs",
        "download_translocs",
        "preview_report",
        "add_sample_comment",
        "add_variant_comment",
        "edit_sample",
        "manage_snvs",
        "manage_cnvs",
        "manage_translocs",
        "assign_tier",
        "hide_sample_comment",
        "unhide_sample_comment",
        "hide_variant_comment",
        "unhide_variant_comment",
        "create_asp",
        "edit_asp",
        "create_aspc",
        "edit_aspc",
        "create_isgl",
        "edit_isgl",
    ],
    "developer": [
        "view_gene_annotations",
        "view_asp",
        "view_aspc",
        "view_isgl",
        "view_reports",
        "download_snvs",
        "download_cnvs",
        "download_translocs",
        "preview_report",
        "add_sample_comment",
        "add_variant_comment",
        "edit_sample",
        "manage_snvs",
        "manage_cnvs",
        "manage_translocs",
        "assign_tier",
        "hide_sample_comment",
        "unhide_sample_comment",
        "hide_variant_comment",
        "unhide_variant_comment",
        "create_asp",
        "edit_asp",
        "create_aspc",
        "edit_aspc",
        "create_isgl",
        "edit_isgl",
        "view_sample_global",
        "delete_sample_global",
    ],
    "admin": BASE_PERMISSION_IDS,
}


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


def _upsert_permission(db, permission_id: str) -> None:
    category = "general"
    for prefix, value in (
        ("view_", "view"),
        ("create_", "create"),
        ("edit_", "edit"),
        ("delete_", "delete"),
        ("download_", "download"),
        ("manage_", "manage"),
        ("hide_", "moderation"),
        ("unhide_", "moderation"),
        ("add_", "annotation"),
        ("assign_", "classification"),
        ("remove_", "classification"),
    ):
        if permission_id.startswith(prefix):
            category = value
            break
    doc = normalize_collection_document(
        "permissions",
        {
            "permission_id": permission_id,
            "permission_name": permission_id,
            "label": permission_id.replace("_", " ").title(),
            "category": category,
            "description": f"{permission_id.replace('_', ' ')} permission",
            "tags": [category],
            "is_active": True,
        },
    )
    db["permissions"].update_one(
        {"permission_id": permission_id},
        {"$set": doc},
        upsert=True,
    )


def _upsert_role(db, role_id: str, permission_ids: list[str]) -> None:
    profile = ROLE_PROFILES.get(
        role_id, {"name": role_id.capitalize(), "level": 9, "color": "#374151"}
    )
    doc = normalize_collection_document(
        "roles",
        {
            "role_id": role_id,
            "name": profile["name"],
            "label": profile["name"],
            "description": f"{profile['name']} role",
            "color": profile["color"],
            "level": profile["level"],
            "is_active": True,
            "permissions": sorted(set(permission_ids)),
            "deny_permissions": [],
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
    email: str,
    password: str,
    role_id: str,
    assay_group: str,
    assay: str,
) -> None:
    username = email.strip().lower()
    fullname = " ".join(part.capitalize() for part in username.split("@")[0].split(".")) or username
    actor = "bootstrap_local_admin"
    now_utc = datetime.now(timezone.utc)
    user_doc = normalize_collection_document(
        "users",
        {
            "email": username,
            "username": username,
            "fullname": fullname,
            "firstname": fullname.split(" ")[0],
            "lastname": " ".join(fullname.split(" ")[1:]) if len(fullname.split(" ")) > 1 else "",
            "job_title": "Center Administrator",
            "auth_type": "coyote3",
            "password": generate_password_hash(password, method="pbkdf2:sha256"),
            "role": role_id,
            "is_active": True,
            "permissions": [],
            "deny_permissions": [],
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
        {"email": username},
        {"$set": user_doc},
        upsert=True,
    )


def main() -> int:
    args = parse_args()
    _fail_if_placeholder_values(args)
    args.role_id = str(args.role_id).strip().lower()
    args.permission_id = str(args.permission_id).strip().lower()
    args.assay_group = str(args.assay_group).strip().lower()
    args.assay = str(args.assay).strip().lower()
    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    client.admin.command("ping")
    db = client[args.db]

    permission_ids = sorted(set(BASE_PERMISSION_IDS + [args.permission_id]))
    for permission_id in permission_ids:
        _upsert_permission(db, permission_id)

    for role_id in ROLE_PROFILES:
        _upsert_role(
            db,
            role_id,
            list(ROLE_BASE_PERMISSIONS.get(role_id, [])),
        )
    if args.role_id not in ROLE_PROFILES:
        _upsert_role(db, args.role_id, [args.permission_id])

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
