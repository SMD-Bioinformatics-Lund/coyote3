#!/usr/bin/env python3
"""Initialize empty Coyote3 application and identity databases before startup.

This is an operator-run deployment step. It connects directly to MongoDB and
never starts Compose services, calls the Coyote3 API, or queues ingest work.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pymongo import MongoClient  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.mongo import configured_mongo_uri  # noqa: E402
from api.contracts.schemas.registry import normalize_collection_document  # noqa: E402
from api.infra.mongo.repositories.clinical_rule_sets import (  # noqa: E402
    build_revision_snapshot,
)
from scripts.build_seed_bundle import (  # noqa: E402
    canonicalize_seed_contract,
    load_reference_seed_pack,
    load_seed,
    lower_business_keys,
    stamp_docs,
)
from scripts.migrate_knowledgebase_database import assert_distinct_databases  # noqa: E402

BOOTSTRAP_ROOT = ROOT_DIR / "api" / "config" / "bootstrap"
DEFAULT_RBAC_DIR = BOOTSTRAP_ROOT / "rbac"
DEFAULT_REFERENCE_DIR = BOOTSTRAP_ROOT / "reference"
DEFAULT_DEMO_CENTER_DIR = BOOTSTRAP_ROOT / "demo_center"


def parse_args() -> argparse.Namespace:
    """Parse database, first-user, and optional demonstration seed settings.

    Returns:
        Process command-line options with bundled seed directories as defaults.

    Raises:
        SystemExit: Required options are missing, arguments are invalid, or help is requested.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mongo-uri", default=configured_mongo_uri(os.environ, "primary"))
    parser.add_argument("--identity-mongo-uri", default=os.getenv("IDENTITY_MONGO_URI", ""))
    parser.add_argument("--db", required=True, help="Application database name")
    parser.add_argument("--identity-db", required=True, help="Identity database name")
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
    """Reject string options containing the deployment placeholder ``change_me``.

    Args:
        args: Parsed options to scan case-insensitively; non-string values are ignored.

    Raises:
        SystemExit: At least one option contains the placeholder; only option names
            are included in the error.
    """
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


def _deployment_is_initialized(db, collection_names: tuple[str, ...]) -> bool:
    """Return whether governance data exists in the target database."""
    return any(db[name].count_documents({}, limit=1) > 0 for name in collection_names)


def _superuser_exists(db, users_collection: str) -> bool:
    """Return whether the target database already has a superuser."""
    return db[users_collection].count_documents({"roles": "superuser"}, limit=1) > 0


def _resolve_directory(value: str, *, label: str) -> Path:
    """Expand and resolve a seed directory, rejecting missing or non-directory paths.

    Args:
        value: Directory path, optionally containing a home-directory prefix.
        label: Operator-facing name used in the failure message.

    Returns:
        Absolute, resolved directory path.

    Raises:
        SystemExit: The resolved path is not a directory.
    """
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

    for collection in (
        "permissions",
        "roles",
        "assay_specific_panels",
        "asp_configs",
        "insilico_genelists",
    ):
        for document in payload.get(collection, []):
            document["system_managed"] = True

    normalized: dict[str, list[dict]] = {}
    for collection, documents in payload.items():
        normalized[collection] = [
            normalize_collection_document(collection, document) for document in documents
        ]
    return normalized


def _make_superuser_document(args: argparse.Namespace, *, actor: str) -> dict:
    """Build a validated local bootstrap user with a hashed password.

    Args:
        args: Options containing username, email, role_id, and plaintext password.
        actor: Identity recorded in creation and update audit fields.

    Returns:
        Normalized user document with lowercase identifiers, the selected role,
        current UTC timestamps, and a required password change.

    Raises:
        pydantic.ValidationError: The user does not satisfy the collection contract.
    """
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
            "system_managed": True,
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
    """Insert a seed batch only when its target collection has no documents.

    Args:
        db: MongoDB database receiving the seed documents.
        collection: Physical collection name.
        documents: Ordered batch to insert; an empty list performs no database access.

    Returns:
        ``empty`` for no input, ``skipped`` for a populated target, or ``loaded``
        after insertion.

    Raises:
        pymongo.errors.PyMongoError: The emptiness check or insertion fails.

    Notes:
        The check and ordered insertion are not atomic; a failed batch may be partial.
    """
    if not documents:
        return "empty"
    if db[collection].count_documents({}, limit=1):
        return "skipped"
    db[collection].insert_many(documents, ordered=True)
    return "loaded"


def _seed_clinical_rule_revisions(
    db, *, rules_collection: str, revisions_collection: str, actor: str
) -> str:
    """Insert a baseline snapshot for each rule set without revision history.

    Args:
        db: Application MongoDB database containing rules and revisions.
        rules_collection: Physical collection of current rule documents.
        revisions_collection: Physical collection receiving immutable snapshots.
        actor: Operator identity recorded on every new baseline.

    Returns:
        ``loaded`` when at least one snapshot was inserted, otherwise ``skipped``.

    Raises:
        pymongo.errors.PyMongoError: Reading rules or writing revisions fails.

    Notes:
        Processes rules in ascending ``_id`` order and uses one UTC timestamp.
        Existing history is left untouched; inserts are not one transaction.
    """
    revisions = db[revisions_collection]
    captured = 0
    occurred_at = datetime.now(timezone.utc)
    for document in db[rules_collection].find({}).sort("_id", 1):
        rule_set_oid = str(document["_id"])
        if revisions.count_documents({"rule_set_oid": rule_set_oid}, limit=1):
            continue
        revisions.insert_one(
            build_revision_snapshot(
                document,
                action="baseline_captured",
                actor=actor,
                occurred_at=occurred_at,
                reason="Initial immutable baseline captured during database bootstrap",
                previous_revision_hash=None,
            )
        )
        captured += 1
    return "loaded" if captured else "skipped"


def _initialize_governance(
    db,
    *,
    seed: dict[str, list[dict]],
    user_document: dict,
    users_collection: str,
    roles_collection: str,
    permissions_collection: str,
) -> str:
    """Populate empty governance collections with bundled RBAC and the first user.

    Args:
        db: Identity MongoDB database receiving governance records.
        seed: Seed mapping containing permissions and roles document lists.
        user_document: Validated first-user document with at least one assigned role.
        users_collection: Physical user collection name.
        roles_collection: Physical role collection name.
        permissions_collection: Physical permission collection name.

    Returns:
        ``skipped`` when governance data and a superuser already exist, or ``loaded``
        after inserting permissions, roles, and the user.

    Raises:
        SystemExit: Governance is partially populated without a superuser, or the
            user's first role is absent from the seed catalog.
        pymongo.errors.PyMongoError: Governance reads or writes fail.

    Notes:
        Writes permissions, then roles, then the user without a transaction.
        Failure can leave partially initialized governance collections.
    """
    collection_names = (users_collection, roles_collection, permissions_collection)
    if _deployment_is_initialized(db, collection_names):
        if _superuser_exists(db, users_collection):
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

    db[permissions_collection].insert_many(seed["permissions"], ordered=True)
    db[roles_collection].insert_many(seed["roles"], ordered=True)
    db[users_collection].insert_one(user_document)
    return "loaded"


def main() -> int:
    """Validate bootstrap inputs and initialize identity and application collections.

    Returns:
        Zero after printing the load or skip status of each selected seed collection.

    Raises:
        SystemExit: CLI parsing exits, placeholders or required inputs are invalid,
            seed directories or collections are missing, or governance cannot be initialized.
        ValueError: Seed normalization fails or database namespaces are not distinct.
        pydantic.ValidationError: Seed or first-user documents violate their contracts.
        OSError: Seed files cannot be read.
        pymongo.errors.PyMongoError: Database checks or bootstrap operations fail.

    Notes:
        Loads demonstration data only when requested. Writes are not transactional
        across collections or databases; both MongoDB clients are closed on exit.
    """
    args = parse_args()
    _fail_if_placeholder_values(args)
    if not args.mongo_uri:
        raise SystemExit("--mongo-uri or COYOTE3_MONGO_URI is required")
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
    primary_mapping = load_collection_section("primary")
    identity_mapping = load_collection_section("identity")

    client = MongoClient(args.mongo_uri, serverSelectionTimeoutMS=7000)
    identity_client = client
    try:
        identity_uri = args.identity_mongo_uri or args.mongo_uri
        if identity_uri != args.mongo_uri:
            identity_client = MongoClient(identity_uri, serverSelectionTimeoutMS=7000)
        client.admin.command("ping")
        identity_client.admin.command("ping")
        db = client[args.db]
        identity_db = identity_client[args.identity_db]
        assert_distinct_databases(db, identity_db)
        governance = _initialize_governance(
            identity_db,
            seed=seed,
            user_document=_make_superuser_document(args, actor=actor),
            users_collection=identity_mapping["users_collection"],
            roles_collection=identity_mapping["roles_collection"],
            permissions_collection=identity_mapping["permissions_collection"],
        )
        print(f"[{governance}] governance: permissions, roles, first superuser")
        primary_collections = {
            "hgnc_genes": primary_mapping["hgnc_collection"],
            "vep_metadata": primary_mapping["vep_metadata_collection"],
            "assay_specific_panels": primary_mapping["asp_collection"],
            "asp_configs": primary_mapping["aspc_collection"],
            "insilico_genelists": primary_mapping["insilico_genelist_collection"],
            "clinical_rule_sets": primary_mapping["clinical_rule_sets_collection"],
            "clinical_rule_revisions": primary_mapping["clinical_rule_revisions_collection"],
        }
        for logical_name in ("hgnc_genes", "vep_metadata"):
            collection = primary_collections[logical_name]
            print(f"[{_insert_if_empty(db, collection, seed[logical_name])}] {logical_name}")
        for logical_name in (
            "assay_specific_panels",
            "clinical_rule_sets",
            "asp_configs",
            "insilico_genelists",
        ):
            if logical_name in seed:
                collection = primary_collections[logical_name]
                print(f"[{_insert_if_empty(db, collection, seed[logical_name])}] {logical_name}")
        if "clinical_rule_sets" in seed:
            result = _seed_clinical_rule_revisions(
                db,
                rules_collection=primary_collections["clinical_rule_sets"],
                revisions_collection=primary_collections["clinical_rule_revisions"],
                actor=actor,
            )
            print(f"[{result}] clinical_rule_revisions")
    finally:
        if identity_client is not client:
            identity_client.close()
        client.close()

    print("[ok] database bootstrap completed; start the Coyote3 application stack next")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
