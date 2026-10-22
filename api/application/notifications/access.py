"""Current clinical authorization for resource-linked inbox messages."""

from collections.abc import Callable
from typing import Any

from api.security.policy import build_access_policy


class SampleNotificationAccess:
    """Resolve current sample ownership and permissions before exposing clinical text."""

    def __init__(self, *, samples: Any, roles: Any, permissions: Any) -> None:
        """Bind repositories without retaining access decisions across requests.

        Args:
            samples: Repository resolving sample IDs to current ownership/scope records.
            roles: Repository supplying current role grants.
            permissions: Catalog used by the shared clinical permission policy.
        """
        self.samples = samples
        self.roles = roles
        self.permissions = permissions

    @classmethod
    def from_store(cls, store: Any) -> "SampleNotificationAccess":
        """Bind the repositories used by clinical routes.

        Args:
            store: Initialized store with sample, role and permission repositories.

        Returns:
            An access resolver without a cross-request authorization cache.
        """
        return cls(
            samples=store.sample_repository,
            roles=store.roles_repository,
            permissions=store.permissions_repository,
        )

    def sample_predicate(self, user: Any) -> Callable[[dict[str, Any]], bool]:
        """Capture current grants for one request or delivery recipient.

        Args:
            user: Authenticated principal or active recipient document represented as an object.

        Returns:
            Predicate applying clinical read permission and sample scope, including superuser access.
        """
        if "superuser" in (getattr(user, "roles", []) or []):
            return lambda sample: bool(sample)
        policy = build_access_policy(
            user=user, roles_repository=self.roles, permissions_repository=self.permissions
        )
        return lambda sample: (
            bool(sample)
            and bool(sample.get("asp_group"))
            and policy.permission_allowed(user, "sample:view", context=sample)
        )

    def inbox_predicate(self, user: Any) -> Callable[[dict[str, Any]], bool]:
        """Authorize clinical messages using current records, caching only within this request.

        Missing or deleted samples hide their notices. Administrative and account messages
        retain their recipient-based visibility. Database errors propagate instead of granting access.

        Args:
            user: Current authenticated principal with role and scope assignments.

        Returns:
            Predicate checking each referenced sample at most once during this request.
        """
        allowed = self.sample_predicate(user)
        decisions: dict[str, bool] = {}

        def visible(document: dict[str, Any]) -> bool:
            """Check a sample-linked notice without exposing its stored resource or message."""
            resource = document.get("resource") or {}
            if resource.get("type") != "sample":
                return True
            identity = str(resource.get("id") or "")
            if not identity:
                return False
            if identity not in decisions:
                sample = self.samples.get_notification_sample(identity)
                decisions[identity] = bool(sample) and allowed(sample)
            return decisions[identity]

        return visible
