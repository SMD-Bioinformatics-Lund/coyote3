# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

"""Read the active MongoDB credential's expanded privilege scope."""

from typing import Any

from pymongo import MongoClient


def authenticated_privileges(uri: str) -> list[dict[str, Any]]:
    """Read expanded privileges using a bounded, short-lived authenticated connection.

    Args:
        uri: Explicit credential-bearing MongoDB URI selected by the caller.

    Returns:
        Expanded privileges, or an empty list when the server supplies none.

    Raises:
        PyMongoError: Connection, authentication or privilege inspection fails.

    Notes:
        Issues connectionStatus with showPrivileges. Does not create collections,
        indexes, users or databases. Closes the client even on failure.
    """
    with MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000) as client:
        return authenticated_client_privileges(client)


def authenticated_client_privileges(client: MongoClient) -> list[dict[str, Any]]:
    """Inspect privileges on the exact client used by the calling repositories.

    Args:
        client: Existing authenticated MongoDB client; its owner controls closing it.

    Returns:
        Expanded authenticated privileges, or an empty list if none were supplied.

    Raises:
        PyMongoError: Authentication or connectionStatus inspection fails.
    """
    status = client.admin.command("connectionStatus", showPrivileges=True)
    return list(status.get("authInfo", {}).get("authenticatedUserPrivileges", []))
