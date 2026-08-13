#!/usr/bin/env python3
"""Initialize an empty Coyote3 database before application services are started.

This is an operator-run deployment step. It connects directly to MongoDB and
never starts Compose services, calls the Coyote3 API, or queues ingest work.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pymongo import MongoClient  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from api.contracts.schemas.registry import normalize_collection_document  # noqa: E402
from scripts.build_seed_bundle import (  # noqa: E402
    canonicalize_seed_contract,
    load_reference_seed_pack,
    load_seed,
    lower_business_keys,
    stamp_docs,
)

BOOTSTRAP_ROOT = ROOT_DIR / "api" / "config" / "bootstrap"
DEFAULT_RBAC_DIR = BOOTSTRAP_ROOT / "rbac"
DEFAULT_REFERENCE_DIR = BOOTSTRAP_ROOT / "reference"
DEFAULT_DEMO_CENTER_DIR = BOOTSTRAP_ROOT / "demo_center"
GOVERNANCE_COLLECTIONS = ("users", "roles", "permissions")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", required=True, help="MongoDB URI with readWrite access")
    parser.add_argument("--db", default="coyote3", help="Application database name")
    parser.add_argument("--username", required=True, help="First local superuser login name")
    parser.add_argument("--email", required=True, help="First local superuser email address")
    parser.add_argument("--password", required=True, help="First local superuser password")
    parser.add_argument("--role-id", default="superuser", help="Bundled role assigned to the user")
    parser.add_argument(
        "--rbac-dir", default=str(DEFAULT_RBAC_DIR), help="Bundled RBAC seed directory"
    )
    parser.add_argument(
        "--reference-dir",
        default=str(DEFAULT_REFERENCE_DIR),
        help="Bundled HGNC and VEP reference seed directory",
    )
    parser.add_argument(
        "--with-demo-center",
        action="store_true",
        help="Also load the synthetic ASP, ASPC, and ISGL demonstration catalog",
    )
    parser.add_argument(
        "--demo-center-dir",
        default=str(DEFAULT_DEMO_CENTER_DIR),
        help="Synthetic or center-owned ASP, ASPC, and ISGL seed directory",
    )
    return parser.parse_args()


def _fail_if_placeholder_values(args: argparse.Namespace) -> None:
    fields = [
        key
        for key, value in vars(args).items()
        if isinstance(value, str) and "change_me" in value.lower()
    ]
    if fields:
        raise SystemExit(
            "Refusing bootstrap because placeholder values were supplied for: "
            + ", ".join(sorted(fields))
        )


def _deployment_is_initialized(db) -> bool:
    """Return whether governance data exists in the target database."""
    return any(db[name].count_documents({}, limit=1) > 0 for name in GOVERNANCE_COLLECTIONS)


def _superuser_exists(db) -> bool:
    """Return whether the target database already has a superuser."""
    return db["users"].count_documents({"roles": "superuser"}, limit=1) > 0


def _resolve_directory(value: str, *, label: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise SystemExit(f"{label} directory was not found: {path}")
    return path


def _build_seed_documents(
    *, rbac_dir: Path, reference_dir: Path, demo_center_dir: Path | None, actor: str
) -> dict[str, list[dict]]:
    """Load, normalize, and validate all selected bootstrap documents before writes."""
    payload = load_reference_seed_pack(rbac_dir)
    payload.update(load_reference_seed_pack(reference_dir))
    if demo_center_dir is not None:
        payload.update(load_seed(demo_center_dir))

    canonicalize_seed_contract(payload)
    lower_business_keys(payload)
    stamp_docs(payload, actor, datetime.now(timezone.utc).isoformat())

    normalized: dict[str, list[dict]] = {}
    for collection, documents in payload.items():
        normalized[collection] = [
            normalize_collection_document(collection, document) for document in documents
        ]
    return normalized


def _make_superuser_document(args: argparse.Namespace, *, actor: str) -> dict:
    username = str(args.username).strip().lower()
    email = str(args.email).strip().lower()
    role_id = str(args.role_id).strip().lower()
    full_name = " ".join(part.capitalize() for part in username.split(".")) or username
    now_utc = datetime.now(timezone.utc)
    return normalize_collection_document(
        "users",
        {
            "email": email,
            "username": username,
            "fullname": full_name,
            "firstname": full_name.split(" ")[0],
            "lastname": " ".join(full_name.split(" ")[1:]),
            "job_title": "Center Bootstrap User",
            "auth_type": ["local"],
            "password": generate_password_hash(args.password, method="pbkdf2:sha256"),
            "roles": [role_id],
            "is_active": True,
            "must_change_password": True,
            "environments": ["production", "development", "testing", "validation"],
            "asp_groups": [],
            "asp_ids": [],
            "created_by": actor,
            "created_on": now_utc,
            "updated_by": actor,
            "updated_on": now_utc,
        },
    )


def _insert_if_empty(db, collection: str, documents: list[dict]) -> str:
    if not documents:
        return "empty"
    if db[collection].count_documents({}, limit=1):
        return "skipped"
    db[collection].insert_many(documents, ordered=True)
    return "loaded"


def _initialize_governance(db, *, seed: dict[str, list[dict]], user_document: dict) -> str:
    if _deployment_is_initialized(db):
        if _superuser_exists(db):
            return "skipped"
        raise SystemExit(
            "Governance collections are partially initialized but no superuser exists. "
            "Inspect the database before retrying; bootstrap will not overwrite it."
        )

    role_ids = {str(document.get("role_id") or "").lower() for document in seed["roles"]}
    assigned_role = str(user_document["roles"][0]).lower()
    if assigned_role not in role_ids:
        raise SystemExit(
            f"Bootstrap role '{assigned_role}' is not present in the bundled RBAC catalog."
        )

    db["permissions"].insert_many(seed["permissions"], ordered=True)
    db["roles"].insert_many(seed["roles"], ordered=True)
    db["users"].insert_one(user_document)
    return "loaded"


def main() -> int:
    args = parse_args()
    _fail_if_placeholder_values(args)
    rbac_dir = _resolve_directory(args.rbac_dir, label="RBAC seed")
    reference_dir = _resolve_directory(args.reference_dir, label="Reference seed")
    demo_center_dir = (
        _resolve_directory(args.demo_center_dir, label="Demo center seed")
        if args.with_demo_center
        else None
    )
    actor = str(args.username).strip().lower()
    seed = _build_seed_documents(
        rbac_dir=rbac_dir,
        reference_dir=reference_dir,
        demo_center_dir=demo_center_dir,
        actor=actor,
    )
    required = {"permissions", "roles", "hgnc_genes", "vep_metadata"}
    missing = sorted(required.difference(seed))
    if missing:
        raise SystemExit("Bootstrap data is missing required collections: " + ", ".join(missing))

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    try:
        client.admin.command("ping")
        db = client[args.db]
        governance = _initialize_governance(
            db, seed=seed, user_document=_make_superuser_document(args, actor=actor)
        )
        print(f"[{governance}] governance: permissions, roles, first superuser")
        for collection in ("hgnc_genes", "vep_metadata"):
            print(f"[{_insert_if_empty(db, collection, seed[collection])}] {collection}")
        for collection in ("assay_specific_panels", "asp_configs", "insilico_genelists"):
            if collection in seed:
                print(f"[{_insert_if_empty(db, collection, seed[collection])}] {collection}")
    finally:
        client.close()

    print("[ok] database bootstrap completed; start the Coyote3 application stack next")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
