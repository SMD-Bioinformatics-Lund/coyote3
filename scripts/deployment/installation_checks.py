"""Read-only installation gates used by the deployment shell orchestrator."""

import argparse
import os
from contextlib import ExitStack

from pymongo import MongoClient

from api.config.collections import load_collection_section
from api.config.mongo import MongoEndpoint, mongo_endpoints


def has_documents(database) -> bool:
    """Return whether a selected database contains any non-system documents.

    Args:
        database: Explicit database handle; empty collections do not count as installed data.

    Returns:
        True on the first populated collection, without reading document contents.
    """
    return any(
        database[name].find_one({}, {"_id": 1}) is not None
        for name in database.list_collection_names()
        if not name.startswith("system.")
    )


def installation_state(primary, identity) -> str:
    """Distinguish empty targets from established or partially initialized installations.

    Args:
        primary: Selected application database.
        identity: Selected identity database, never inferred from a database name.

    Returns:
        fresh if both databases contain no documents; existing when the identity
        baseline is complete, including before authenticated application seeding.

    Raises:
        ValueError: Only part of the required baseline exists; automatic bootstrap is unsafe.
    """
    populated = has_documents(primary), has_documents(identity)
    if not any(populated):
        return "fresh"
    mapping = load_collection_section("identity")
    users = identity[mapping["users_collection"]]
    complete = (
        populated[1]
        and users.find_one({"roles": "superuser"}, {"_id": 1}) is not None
        and users.find_one({"roles": "sys_admin"}, {"_id": 1}) is not None
        and identity[mapping["roles_collection"]].find_one({}, {"_id": 1}) is not None
        and identity[mapping["permissions_collection"]].find_one({}, {"_id": 1}) is not None
    )
    if not complete:
        raise ValueError(
            "Partial or unrecognized installation: automatic bootstrap refused. "
            "Inspect the selected application and identity databases; do not reset them."
        )
    return "existing"


def validate_configuration() -> None:
    """Validate mounted center definitions without connecting to any database."""
    from api.config.contact import load_contact_config
    from api.config.paths import CONTACT_CONFIG_PATH
    from coyote3.config.clinical_vocabulary import load_clinical_vocabulary
    from coyote3.config.loaders.filter_flags import load_filter_flag_metadata

    load_clinical_vocabulary()
    load_filter_flag_metadata()
    load_contact_config(
        CONTACT_CONFIG_PATH, organization_name="Validation", public_base_url="", script_name=""
    )


def check_endpoints() -> str:
    """Validate four configured transaction-capable endpoints and inspect target state.

    Returns:
        fresh or existing after all servers pass read-only connectivity checks.

    Raises:
        ValueError: Endpoint authentication, topology or installation state is unsuitable.
    """
    endpoints = mongo_endpoints(os.environ)
    with ExitStack() as stack:
        databases = {}
        for service, endpoint in endpoints.items():
            try:
                client = stack.enter_context(
                    MongoClient(endpoint.uri, serverSelectionTimeoutMS=7000)
                )
                hello = client.admin.command("hello")
                if not hello.get("isWritablePrimary") or not (
                    hello.get("setName") or hello.get("msg") == "isdbgrid"
                ):
                    raise ValueError("Writable replica-set primary or mongos required")
                databases[service] = client[endpoint.database]
                # Verify database read access as well as server reachability.
                databases[service].list_collection_names()
            except Exception as error:
                raise ValueError(
                    f"{service} endpoint check failed ({type(error).__name__})"
                ) from None
        return installation_state(databases["primary"], databases["identity"])


def validate_maintenance_endpoint() -> None:
    """Reject maintenance credentials that select a different knowledgebase server.

    Raises:
        ValueError: The maintenance URI changes the configured server or replica set.
    """
    runtime = mongo_endpoints(os.environ)["knowledgebase"]
    maintenance = MongoEndpoint(os.environ.get("COYOTE_INSTALL_KB_URI", ""), runtime.database)
    if runtime.namespace != maintenance.namespace:
        raise ValueError("Knowledgebase maintenance URI must use the runtime hosts and replica set")


def check_indexes(*, require_present: bool = False, scope: str = "application") -> None:
    """Summarize index state and identify contracts that block installation.

    Args:
        require_present: Also reject missing indexes after index application.
        scope: application, knowledgebase or all index ownership groups.

    Raises:
        ValueError: Indexes conflict, or required indexes remain missing after application.
    """
    from api.infra.mongo.index_management import build_index_plan
    from scripts.database.manage_mongo_indexes import _adapter

    adapter = _adapter(scope)
    try:
        plan = build_index_plan(adapter, include_security=scope != "knowledgebase")
    finally:
        adapter.close()
    counts = {
        state: sum(item["state"] == state for item in plan)
        for state in ("present", "missing", "conflict")
    }
    print("[indexes] " + " ".join(f"{state}={count}" for state, count in counts.items()))
    failures = [
        item
        for item in plan
        if item["state"] == "conflict" or (require_present and item["state"] == "missing")
    ]
    for item in failures:
        print(
            f"[{item['state']}] repository={item['repository']} "
            f"collection={item['collection']} index={item['name']}"
        )
    if failures:
        raise ValueError(
            "Required indexes are not ready; application startup refused. "
            "Inspect the named contracts with scripts/database/manage_mongo_indexes.py status."
        )


def check_redis() -> None:
    """Verify authenticated Redis access from the application container.

    Raises:
        ValueError: A required Redis URL is missing or its PING fails. Messages
            identify the setting and exception type without disclosing credentials.
    """
    import redis

    for key in ("CACHE_REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
        url = os.environ.get(key)
        if not url:
            raise ValueError(f"{key} is required for the Redis connectivity check")
        try:
            with redis.Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3) as client:
                client.ping()
        except Exception as error:
            raise ValueError(
                f"{key} PING failed ({type(error).__name__}). "
                "Redis must be reachable from application containers, not only from its own "
                "health check. Check credentials for authentication errors; for connection "
                "timeouts inspect Docker bridge forwarding and host firewall policy. "
                "See docs/operations/troubleshooting.md."
            ) from None
    print("[ok] Redis cache, broker and result backend are reachable")


def main() -> int:
    """Run one installation gate; suppress connection details in error messages.

    Returns:
        Zero on success or one on failure. State is printed only after all checks pass.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=("configuration", "state", "maintenance", "indexes", "indexes-ready", "redis"),
    )
    parser.add_argument(
        "--scope", choices=("application", "knowledgebase", "all"), default="application"
    )
    args = parser.parse_args()
    try:
        if args.operation == "configuration":
            validate_configuration()
        elif args.operation == "state":
            print(check_endpoints())
        elif args.operation == "maintenance":
            validate_maintenance_endpoint()
        elif args.operation == "redis":
            check_redis()
        else:
            check_indexes(require_present=args.operation == "indexes-ready", scope=args.scope)
    except Exception as error:
        # Driver errors may contain credentials or operational addresses.
        print(f"Installation {args.operation} check failed ({type(error).__name__}).")
        if isinstance(error, ValueError) and args.operation in {
            "state",
            "maintenance",
            "indexes",
            "indexes-ready",
            "redis",
        }:
            print(str(error))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
