#!/usr/bin/env python3
"""Install initial accounts, bundled catalogs, knowledgebases and demos on fresh targets.

This is an operator-run deployment step. It connects directly to MongoDB and
never starts Compose services, calls the Coyote3 API, or queues ingest work.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from pymongo import MongoClient  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from api.config.loaders.collections import load_collection_section  # noqa: E402
from api.config.mongo import configured_mongo_uri  # noqa: E402
from api.contracts.schemas.registry import normalize_collection_document  # noqa: E402
from api.infra.seed.documents import build_seed_documents  # noqa: E402

BOOTSTRAP_ROOT = ROOT_DIR / "api" / "config" / "bootstrap"
DEFAULT_RBAC_DIR = BOOTSTRAP_ROOT / "rbac"
DEFAULT_REFERENCE_DIR = BOOTSTRAP_ROOT / "reference"


def parse_args() -> argparse.Namespace:
    """Parse database, first-user, and optional demonstration seed settings.

    Returns:
        Process command-line options with bundled seed directories as defaults.

    Raises:
        SystemExit: Required options are missing, arguments are invalid, or help is requested.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-empty-target",
        action="store_true",
        help="Refuse all bootstrap writes if application or identity documents already exist",
    )
    parser.add_argument("--mongo-uri", default=configured_mongo_uri(os.environ, "primary"))
    parser.add_argument("--identity-mongo-uri", default=os.getenv("IDENTITY_MONGO_URI", ""))
    parser.add_argument("--db", required=True, help="Application database name")
    parser.add_argument("--identity-db", required=True, help="Identity database name")
    parser.add_argument("--username", help="First local superuser login name")
    parser.add_argument("--email", help="First local superuser email address")
    parser.add_argument("--password", help="Temporary superuser password; omit for a hidden prompt")
    parser.add_argument("--role-id", default="superuser", choices=["superuser"])
    parser.add_argument("--sys-admin-username", help="Named initial system administrator")
    parser.add_argument("--sys-admin-email", help="System administrator email")
    parser.add_argument(
        "--sys-admin-password", help="Temporary system-admin password; omit for a hidden prompt"
    )
    parser.add_argument(
        "--rbac-dir", default=str(DEFAULT_RBAC_DIR), help="Bundled RBAC seed directory"
    )
    parser.add_argument(
        "--reference-dir",
        default=str(DEFAULT_REFERENCE_DIR),
        help="Bundled application catalog and knowledgebase seed directory",
    )
    for module in ("users", "application", "knowledgebase", "demo"):
        parser.add_argument(f"--skip-{module}", action="store_true")
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


def _make_bootstrap_user(args: argparse.Namespace, *, actor: str) -> dict:
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


def _initialize_governance(
    db,
    *,
    seed: dict[str, list[dict]],
    user_document: dict,
    system_admin_document: dict,
    users_collection: str,
    roles_collection: str,
    permissions_collection: str,
) -> str:
    """Populate empty governance collections with RBAC and two distinct initial accounts.

    Args:
        db: Identity MongoDB database receiving governance records.
        seed: Seed mapping containing permissions and roles document lists.
        user_document: Validated first-user document with at least one assigned role.
        system_admin_document: Validated named system-administrator document.
        users_collection: Physical user collection name.
        roles_collection: Physical role collection name.
        permissions_collection: Physical permission collection name.

    Returns:
        ``skipped`` when governance data and a superuser already exist, or ``loaded``
        after inserting permissions, roles, and both initial accounts.

    Raises:
        SystemExit: Governance is partially populated without a superuser, or the
            user's first role is absent from the seed catalog.
        pymongo.errors.PyMongoError: Governance reads or writes fail.

    Notes:
        Creates declared indexes, then commits permissions, roles, and both accounts
        in one identity-database transaction. Concurrent initialization cannot create
        duplicate role or user identifiers.
    """
    collection_names = (users_collection, roles_collection, permissions_collection)
    if _deployment_is_initialized(db, collection_names):
        if _superuser_exists(db, users_collection):
            return "skipped"
        raise SystemExit(
            "Governance collections are partially initialized but no superuser exists. "
            "Inspect the database before retrying; bootstrap will not overwrite it."
        )

    if user_document["username"] == system_admin_document["username"]:
        raise SystemExit("Superuser and system administrator must be different accounts")
    if user_document["roles"] != ["superuser"] or system_admin_document["roles"] != ["sys_admin"]:
        raise SystemExit("Bootstrap requires exactly one superuser and one system administrator")
    role_ids = {str(document.get("role_id") or "").lower() for document in seed["roles"]}
    if "sys_admin" not in role_ids:
        raise SystemExit("The bundled system administrator role is missing")
    assigned_role = str(user_document["roles"][0]).lower()
    if assigned_role not in role_ids:
        raise SystemExit(
            f"Bootstrap role '{assigned_role}' is not present in the bundled RBAC catalog."
        )

    from api.infra.mongo.transactions import run_transaction

    def initialize(session):
        """Commit both accounts and their permission definitions together."""
        if any(db[name].count_documents({}, limit=1, session=session) for name in collection_names):
            raise SystemExit("Governance changed during bootstrap; no records were overwritten")
        db[permissions_collection].insert_many(seed["permissions"], ordered=True, session=session)
        db[roles_collection].insert_many(seed["roles"], ordered=True, session=session)
        db[users_collection].insert_many([user_document, system_admin_document], session=session)

    from api.infra.mongo.repositories.permissions import PermissionsRepository
    from api.infra.mongo.repositories.roles import RolesRepository
    from api.infra.mongo.repositories.users import UsersRepository

    adapter = SimpleNamespace(
        users_collection=db[users_collection],
        roles_collection=db[roles_collection],
        permissions_collection=db[permissions_collection],
    )
    for repository in (
        UsersRepository(adapter),
        RolesRepository(adapter),
        PermissionsRepository(adapter),
    ):
        repository.ensure_indexes()
    run_transaction(db.client, initialize)
    return "loaded"


def _install_initial_data(databases: dict, seed: dict, args: argparse.Namespace) -> None:
    """Install selected packaged modules only after this invocation created the accounts.

    Args:
        databases: Explicit primary, identity and knowledgebase database handles.
        seed: Validated documents attributed to the system actor.
        args: Initial installation module skip flags.
    """
    from api.infra.mongo.repositories.deployment_data import DeploymentDataRepository

    repository = DeploymentDataRepository(
        databases["primary"], databases["knowledgebase"], databases["identity"]
    )
    for module in ("application", "knowledgebase"):
        if not getattr(args, f"skip_{module}", False):
            results = repository.install(seed, scope=module, actor="system")
            for name, status in results.items():
                print(f"[{status}] {name}")
    if not getattr(args, "skip_demo", False):
        from scripts.bootstrap.demo_service import build_demo_service

        result = build_demo_service(
            databases["primary"], databases["knowledgebase"]
        ).install_starter("system", created_by="system")
        print(f"[{result['status']}] demo")


def main() -> int:
    """Install the selected default modules once on a fresh deployment.

    Returns:
        Zero after installation or after preserving an existing deployment.

    Raises:
        SystemExit: Inputs conflict, the target is partial, or a dependency was skipped.
        ValueError: Seed validation, namespace checks or database operations fail.

    Notes:
        Only the invocation that creates initial governance may seed without API login.
        Once accounts exist, later additions and repairs use manage_data.py.
    """
    from api.infra.mongo.connections import MongoConnections
    from scripts.deployment.installation_checks import has_documents, installation_state

    args = parse_args()
    _fail_if_placeholder_values(args)
    if getattr(args, "skip_users", False) and not all(
        getattr(args, f"skip_{module}", False)
        for module in ("application", "knowledgebase", "demo")
    ):
        raise SystemExit("--skip-users requires skipping application, knowledgebase and demo data")
    if getattr(args, "skip_application", False) and not getattr(args, "skip_demo", False):
        raise SystemExit("--skip-application requires --skip-demo")
    config = {
        **os.environ,
        "COYOTE3_MONGO_URI": args.mongo_uri or "",
        "IDENTITY_MONGO_URI": args.identity_mongo_uri or args.mongo_uri or "",
        "COYOTE3_DB": args.db,
        "IDENTITY_DB": args.identity_db,
    }
    connections = MongoConnections(config, client_factory=MongoClient)
    try:
        databases = connections.databases
        primary, identity = databases["primary"], databases["identity"]
        state = installation_state(primary, identity)
        if state == "existing":
            print(
                "[skipped] Existing deployment; use manage_data.py for authenticated additions or repairs."
            )
            return 0
        if getattr(args, "skip_users", False):
            print("[skipped] Initial users and deployment data were disabled.")
            return 0
        for field, prompt in (
            ("sys_admin_username", "Named administrator username: "),
            ("sys_admin_email", "Named administrator email: "),
            ("username", "Emergency superuser username: "),
            ("email", "Emergency superuser email: "),
        ):
            if not getattr(args, field):
                setattr(args, field, input(prompt).strip())
        if args.username.strip().lower() == args.sys_admin_username.strip().lower():
            raise SystemExit("Superuser and system administrator logins must be different")
        if args.email.strip().lower() == args.sys_admin_email.strip().lower():
            raise SystemExit("Use distinct email addresses for the two bootstrap accounts")
        for field, label in (
            ("password", "Superuser"),
            ("sys_admin_password", "System administrator"),
        ):
            if not getattr(args, field):
                password = getpass.getpass(f"{label} temporary password: ")
                if password != getpass.getpass(f"Confirm {label.lower()} temporary password: "):
                    raise SystemExit("Password confirmation does not match")
                setattr(args, field, password)
            if len(getattr(args, field)) < 12:
                raise SystemExit("Temporary passwords must contain at least 12 characters")
        if args.password == args.sys_admin_password:
            raise SystemExit("Use different temporary passwords for the two bootstrap accounts")
        _fail_if_placeholder_values(args)
        seed = build_seed_documents(
            rbac_dir=_resolve_directory(args.rbac_dir, label="RBAC seed"),
            reference_dir=_resolve_directory(args.reference_dir, label="Reference seed"),
            actor="system",
            include_knowledgebase=not getattr(args, "skip_knowledgebase", False),
        )
        if not getattr(args, "skip_knowledgebase", False):
            from api.infra.seed.diagrams import load_seed_diagrams

            seed["vep_diagrams"] = load_seed_diagrams(
                seed["vep_metadata"], Path(args.reference_dir).expanduser().resolve()
            )
        if has_documents(primary) or has_documents(identity):
            raise SystemExit(
                "Target changed during installation; no bootstrap writes were performed"
            )
        mapping = load_collection_section("identity")
        governance = _initialize_governance(
            identity,
            seed=seed,
            user_document=_make_bootstrap_user(args, actor="system"),
            system_admin_document=_make_bootstrap_user(
                argparse.Namespace(
                    username=args.sys_admin_username,
                    email=args.sys_admin_email,
                    password=args.sys_admin_password,
                    role_id="sys_admin",
                ),
                actor="system",
            ),
            users_collection=mapping["users_collection"],
            roles_collection=mapping["roles_collection"],
            permissions_collection=mapping["permissions_collection"],
        )
        print(f"[{governance}] governance: permissions, roles, superuser and system administrator")
        if governance == "loaded":
            audit_environment = {
                "IDENTITY_DB": args.identity_db,
                "IDENTITY_MONGO_URI": config["IDENTITY_MONGO_URI"],
            }
            previous_environment = {key: os.environ.get(key) for key in audit_environment}
            try:
                os.environ.update(audit_environment)
                _install_initial_data(databases, seed, args)
            except Exception:
                print(
                    "Initial accounts exist. Complete missing modules through manage_data.py "
                    "after starting the API.",
                    file=sys.stderr,
                )
                raise
            finally:
                for key, value in previous_environment.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value
    finally:
        connections.close()
    print("[ok] Initial installation completed; change temporary passwords at first sign-in.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
