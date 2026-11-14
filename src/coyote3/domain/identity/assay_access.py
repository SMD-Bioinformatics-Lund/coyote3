"""Exact assay/environment grants shared by application and host access policies."""

from typing import Any


def grants_for(user: Any) -> list[dict[str, Any]] | None:
    """Return current explicit grants; only a superuser has unrestricted scope.

    Args:
        user: Trusted actor or persisted identity mapping.

    Returns:
        Explicit grant rows, an empty list for no grants, or None for a superuser.
        Legacy independent allowance lists never provide access.
    """
    mapping = isinstance(user, dict)
    roles = user.get("roles", []) if mapping else getattr(user, "roles", [])
    if (isinstance(roles, (list, tuple, set, frozenset)) and "superuser" in roles) or (
        not mapping and getattr(user, "is_superuser", False) is True
    ):
        return None
    rows = user.get("assay_access", []) if mapping else getattr(user, "assay_access", [])
    if not isinstance(rows, (list, tuple)):
        return []
    result = []
    for row in rows:
        row = row.model_dump() if hasattr(row, "model_dump") else row
        if not isinstance(row, dict) or not isinstance(row.get("asp_id"), str):
            return []
        envs = row.get("environments")
        if not isinstance(envs, list) or any(
            not isinstance(env, str) or not env.strip() for env in envs
        ):
            return []
        result.append({"asp_id": row["asp_id"], "environments": list(envs)})
    return result


def pair_allowed(
    grants: list[dict[str, Any]] | None, asp_id: str = "", environment: str = ""
) -> bool:
    """Match supplied attributes against one grant row, never across separate rows.

    Args:
        grants: Explicit grants or None for an already verified superuser.
        asp_id: Assay ID; blank supports an environment-only preflight.
        environment: Environment ID; blank supports an assay-only preflight.

    Returns:
        Whether one row grants all supplied attributes. Attribute-free preflight is allowed.
    """
    if grants is None or not (asp_id or environment):
        return True
    return any(
        (not asp_id or row.get("asp_id") == asp_id)
        and bool(row.get("environments"))
        and (not environment or environment in row["environments"])
        for row in grants
    )


def scope_projection(grants: list[dict[str, Any]] | None) -> tuple[list[str], list[str]]:
    """Derive navigation choices, never an authorization filter, from explicit grants.

    Args:
        grants: Explicit rows; unrestricted actors are handled by their calling policy.

    Returns:
        Granted assay IDs and environment IDs for selectors.
    """
    rows = [row for row in grants or [] if row.get("environments")]
    return (
        sorted({row["asp_id"] for row in rows}),
        sorted({env for row in rows for env in row["environments"]}),
    )
