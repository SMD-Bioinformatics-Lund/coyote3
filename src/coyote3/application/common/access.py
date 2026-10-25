"""Permission and sample-scope checks shared by HTTP and local application callers."""

from collections.abc import Callable
from typing import Any, Protocol

from coyote3.domain.common.errors import api_error


class ScopePolicy(Protocol):
    """Evaluate current role grants and resource attribute assignments."""

    def permission_allowed(
        self, user: Any, permission_id: str, *, context: dict[str, Any] | None = None
    ) -> bool:
        """Return whether current grants allow this operation and optional resource scope."""
        ...

    def scope_allowed(self, user: Any, context: dict[str, Any] | None) -> bool:
        """Return whether all supplied resource attributes are assigned to the actor."""
        ...


def enforce_access(
    user: Any,
    *,
    permission: str | None,
    context: dict[str, Any] | None = None,
    policy_factory: Callable[[Any], ScopePolicy],
    internal_ingest: bool = False,
) -> None:
    """Enforce current permission and attribute grants without an HTTP dependency.

    Args:
        user: Identity established by a trusted authentication adapter.
        permission: Registered permission, or None for an authenticated scope check.
        context: Resource attributes, or None before a resource has been loaded.
        policy_factory: Resolves current role and permission documents for this actor.
        internal_ingest: Whether the trusted adapter authenticated an ingest credential.

    Raises:
        AppError: The credential is outside its audience or current grants deny access.
    """
    if internal_ingest:
        if permission not in {None, "internal.ingest:manage", "sample:edit:own"}:
            raise api_error(
                403,
                "Ingestion credentials are limited to sample ingestion operations",
                category="scope",
            )
        return
    if user.is_superuser or (not permission and not context):
        return
    policy = policy_factory(user)
    if permission and not policy.permission_allowed(user, permission, context=context):
        raise api_error(
            403,
            "Access denied",
            "You do not satisfy the required permission policy.",
            category="auth",
        )
    if context and not policy.scope_allowed(user, context):
        raise api_error(
            403,
            "Access denied",
            "You do not satisfy the required attribute-scope policy.",
            category="scope",
        )


def sample_scope_allowed(
    user: Any,
    sample: dict[str, Any],
    *,
    policy_factory: Callable[[Any], ScopePolicy],
    assay_loader: Callable[[str], dict[str, Any] | None],
) -> bool:
    """Apply the established assay, environment and biological-group sample policy.

    Args:
        user: Authenticated actor with current attribute assignments.
        sample: Authoritative sample record loaded by the application.
        policy_factory: Resolves the current access policy, without a decision cache.
        assay_loader: Loads the registered assay when group membership is restricted.

    Returns:
        True for a superuser or a sample matching every applicable attribute grant.
    """
    if user.is_superuser:
        return True
    assay_id = sample.get("asp_id", "")
    group_restricted = bool(user.asp_groups) and "*" not in user.asp_groups
    assay = assay_loader(assay_id) if group_restricted else None
    group = assay.get("asp_group") if assay else None
    return (not group_restricted or bool(group)) and policy_factory(user).scope_allowed(
        user,
        {"asp_id": assay_id, "environment": sample.get("environment"), "asp_group": group},
    )


def enforce_assay_group(user: Any, group: str) -> None:
    """Apply the existing explicit group-assignment requirement for coverage curation.

    Args:
        user: Verified current identity, including biological-group assignments.
        group: Exact registered biological group requested by the operation.

    Raises:
        AppError: A non-superuser is not explicitly assigned to the requested group.
    """
    if not user.is_superuser and group not in set(user.asp_groups or []):
        raise api_error(
            403,
            f"Assay group '{group}' is outside your scope",
            f"User '{user.username}' is not assigned to assay group '{group}'.",
            category="scope",
            hint="Ask an administrator to assign the assay group, or use a superuser account.",
        )
