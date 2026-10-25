#!/usr/bin/env python3
"""Export the bundled role policy or explicitly harden one runtime MongoDB user."""

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pymongo import MongoClient  # noqa: E402
from pymongo.errors import PyMongoError  # noqa: E402
from pymongo.uri_parser import parse_uri  # noqa: E402

from api.config.mongo import MongoEndpoint, mongo_endpoints  # noqa: E402
from api.infra.security.mongo_roles import (  # noqa: E402
    audit_indexes,
    identity_role,
    provision_identity,
    runtime_roles,
)

POLICY = ROOT / "deploy/compose/mongo-init/identity-role-policy.json"


def runtime_principal(config: dict[str, str]) -> tuple[str, str]:
    """Select the username and authentication database from the runtime identity URI.

    Args:
        config: Explicit MongoDB endpoint configuration; passwords are never returned.

    Returns:
        Username and authSource, falling back to the URI path or admin as PyMongo does.
        The username is empty when the URI contains no username.
    """
    parsed = parse_uri(mongo_endpoints(config)["identity"].uri)
    auth_database = parsed["options"].get("authSource") or parsed["database"] or "admin"
    return parsed["username"] or "", auth_database


def policy_text() -> str:
    """Serialize the shared policy for the first-initialization MongoDB script."""
    return (
        json.dumps(
            {"identity_role": identity_role("identity"), "indexes": audit_indexes()},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> int:
    """Export/check policy, or plan/apply a privileged runtime-role upgrade.

    Returns:
        Zero on success; nonzero on stale policy, invalid configuration or database errors.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--export-policy", action="store_true")
    mode.add_argument("--check-policy", action="store_true")
    credentials = parser.add_mutually_exclusive_group()
    credentials.add_argument("--maintenance-uri-file", type=Path)
    credentials.add_argument(
        "--maintenance-uri-env", help="Name of an ephemeral maintenance-URI environment variable"
    )
    parser.add_argument(
        "--username", help="Runtime username; defaults to the configured identity URI"
    )
    parser.add_argument(
        "--authentication-database",
        help="Defaults to the configured identity URI's authentication database",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Replace the selected user's roles with the reviewed runtime policy",
    )
    args = parser.parse_args()
    if args.export_policy:
        POLICY.write_text(policy_text())
        return 0
    if args.check_policy:
        return 0 if POLICY.read_text() == policy_text() else 1
    names = {
        key: os.environ.get(key, "").strip()
        for key in ("COYOTE3_DB", "IDENTITY_DB", "KNOWLEDGEBASE_DB", "BAM_DB")
    }
    if not (args.maintenance_uri_file or args.maintenance_uri_env) or not all(names.values()):
        parser.error("Set four database names and provide maintenance credentials")
    try:
        roles = runtime_roles(dict(os.environ))
        configured_username, configured_auth_database = runtime_principal(dict(os.environ))
    except RuntimeError as error:
        parser.error(str(error))
    except ValueError:
        parser.error("Invalid MongoDB identity connection settings")
    except PyMongoError:
        parser.error("Cannot resolve MongoDB identity connection settings")
    args.username = args.username or configured_username
    args.authentication_database = args.authentication_database or configured_auth_database
    if not args.username:
        parser.error("Provide --username or include the runtime username in the identity URI")
    print(
        json.dumps(
            {
                "username": args.username,
                "authentication_database": args.authentication_database,
                "replacement_roles": roles,
                "apply": args.apply,
            },
            indent=2,
        )
    )
    if not args.apply:
        return 0
    try:
        uri = (
            args.maintenance_uri_file.read_text()
            if args.maintenance_uri_file
            else os.environ.get(args.maintenance_uri_env, "")
        ).strip()
        if not uri:
            raise ValueError("Maintenance URI is empty")
        expected = mongo_endpoints(os.environ)["identity"]
        if MongoEndpoint(uri, names["IDENTITY_DB"]).namespace != expected.namespace:
            raise ValueError(
                "Maintenance credentials must target the configured identity deployment"
            )
        with MongoClient(uri, serverSelectionTimeoutMS=10000) as client:
            auth = client[args.authentication_database]
            authenticated = client.admin.command("connectionStatus")["authInfo"][
                "authenticatedUsers"
            ]
            if any(
                user["user"] == args.username and user["db"] == args.authentication_database
                for user in authenticated
            ):
                raise ValueError("Maintenance and runtime users must be distinct")
            if not auth.command("usersInfo", args.username)["users"]:
                raise ValueError("Selected runtime user does not exist")
            provision_identity(client[names["IDENTITY_DB"]])
            auth.command("updateUser", args.username, roles=roles)
    except (OSError, ValueError, PyMongoError) as error:
        print(
            f"Role upgrade failed ({type(error).__name__}); inspect the selected target and maintenance privileges.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
