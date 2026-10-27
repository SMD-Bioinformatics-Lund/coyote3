"""Collection-scoped MongoDB runtime privileges and protected audit provisioning."""

import logging
from typing import Any

from pymongo.errors import OperationFailure

from api.config.collections import load_collection_section
from api.config.mongo import mongo_endpoints
from api.config.operational_collections import OPERATIONAL_COLLECTIONS
from api.infra.security.indexes import security_index_contracts

IDENTITY_ROLE = "coyote3_runtime_identity"
logger = logging.getLogger(__name__)


def runtime_roles(config: dict[str, Any]) -> list[dict[str, str]]:
    """Grant access only to logical services on the configured identity deployment.

    Args:
        config: Explicit MongoDB URI/name settings for all four services.

    Returns:
        Restricted identity role and required data/reference roles on the same deployment.
        Independent deployments do not receive grants merely because database names match.

    Raises:
        RuntimeError: Endpoint configuration is missing or namespaces overlap.
    """
    endpoints = mongo_endpoints(config)
    identity = endpoints["identity"]
    roles = [{"role": IDENTITY_ROLE, "db": identity.database}]
    for service in ("primary", "bam", "knowledgebase"):
        endpoint = endpoints[service]
        if endpoint.namespace[:2] == identity.namespace[:2]:
            roles.append(
                {
                    "role": "read" if service == "knowledgebase" else "readWrite",
                    "db": endpoint.database,
                }
            )
    return roles


def verify_runtime_audit_permissions(client: Any, database: str) -> None:
    """Warn for unprotected MongoDB and reject destructive authenticated audit grants.

    Args:
        client: Identity connection, optionally authenticated as the runtime user.
        database: Configured identity namespace.

    Raises:
        ValueError: Authenticated runtime privileges allow audit mutation or role administration.
        PyMongoError: MongoDB cannot return effective session privileges.

    Notes:
        A query-planner-only explain checks update authorization without modifying data.
        This also detects servers that accept credentials but have authorization disabled.
    """
    info = client.admin.command("connectionStatus", showPrivileges=True)["authInfo"]
    if not info.get("authenticatedUsers"):
        logger.warning(
            "Identity MongoDB connection is unauthenticated; continuing without database-level "
            "audit protection. Application login and role permissions still apply."
        )
        return
    audit = load_collection_section("identity")["audit_events_collection"]
    destructive = {
        "anyAction",
        "update",
        "remove",
        "dropCollection",
        "dropDatabase",
        "dropIndex",
        "createIndex",
        "collMod",
        "renameCollectionSameDB",
        "convertToCapped",
    }
    for privilege in info.get("authenticatedUserPrivileges", []):
        if {
            "grantRole",
            "revokeRole",
            "createRole",
            "updateRole",
            "dropRole",
            "internal",
        }.intersection(privilege["actions"]):
            raise ValueError(
                "Identity runtime must not have MongoDB role-administration privileges"
            )
        resource = privilege["resource"]
        covers_audit = resource.get("anyResource") or (
            resource.get("db") in {"", database} and resource.get("collection") in {"", audit}
        )
        if covers_audit and destructive.intersection(privilege["actions"]):
            raise ValueError(
                "Identity runtime grants can alter retained audit history; apply the restricted MongoDB role policy"
            )
    try:
        client[database].command(
            "explain",
            {
                "update": audit,
                "updates": [
                    {
                        "q": {"_id": {"$exists": False}},
                        "u": {"$set": {"message": "audit-permission-probe"}},
                    },
                ],
            },
            verbosity="queryPlanner",
        )
    except OperationFailure as error:
        if error.code == 13:
            return
        raise
    logger.warning("MongoDB authorization is not enforcing retained audit protection; continuing.")


def identity_role(database: str) -> dict[str, Any]:
    """Build the runtime identity role without clinical-audit mutation privileges.

    Args:
        database: Explicit identity database namespace.

    Returns:
        Custom role definition. Clinical events permit find/insert/listIndexes only;
        chain heads are mutable, and operational events can undergo retention cleanup.
    """
    mapping = load_collection_section("identity")
    mutable = {value for key, value in mapping.items() if key != "audit_events_collection"}
    privileges = [
        {
            "resource": {"db": database, "collection": name},
            "actions": ["find", "insert", "update", "remove", "createIndex", "listIndexes"],
        }
        for name in sorted(mutable)
    ]
    for name, actions in (
        (OPERATIONAL_COLLECTIONS.audit_chain_heads, ["find", "insert", "update"]),
        (OPERATIONAL_COLLECTIONS.audit_outbox, ["find", "insert", "remove"]),
        (
            OPERATIONAL_COLLECTIONS.operational_audit_events,
            ["find", "insert", "remove", "createIndex", "listIndexes"],
        ),
    ):
        privileges.append({"resource": {"db": database, "collection": name}, "actions": actions})
    privileges.append(
        {
            "resource": {"db": database, "collection": mapping["audit_events_collection"]},
            "actions": ["find", "insert", "listIndexes"],
        }
    )
    privileges.append(
        {
            "resource": {"db": database, "collection": ""},
            "actions": ["listCollections"],
        }
    )
    return {"role": IDENTITY_ROLE, "privileges": privileges, "roles": []}


def audit_indexes() -> list[dict[str, Any]]:
    """Return protected audit indexes for privileged installation, never runtime writes."""
    mapping = load_collection_section("identity")
    config = {"DB_COLLECTIONS_CONFIG": {"identity": mapping}}
    return [
        {
            "collection": contract.collection,
            "fields": list(contract.fields),
            "name": contract.name,
            **contract.options,
        }
        for contract in security_index_contracts(config)
        if contract.collection == mapping["audit_events_collection"]
    ]


def provision_identity(database: Any) -> None:
    """Install audit indexes and the restricted role using maintenance credentials.

    Args:
        database: Identity database handle authenticated with role/index administration rights.

    Raises:
        PyMongoError: MongoDB rejects index or role provisioning.

    Notes:
        Does not rewrite events or change any existing user's role assignments.
    """
    for index in audit_indexes():
        spec = dict(index)
        collection = spec.pop("collection")
        fields = [tuple(field) for field in spec.pop("fields")]
        database[collection].create_index(fields, **spec)
    role = identity_role(database.name)
    command = (
        "updateRole" if database.command("rolesInfo", IDENTITY_ROLE)["roles"] else "createRole"
    )
    database.command(command, IDENTITY_ROLE, privileges=role["privileges"], roles=[])
