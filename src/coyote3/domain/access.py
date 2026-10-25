"""Authorization interfaces independent of enforcement engines and HTTP transports."""

from typing import Any, Protocol


class AccessPolicy(Protocol):
    """Check a permission against a principal and current resource scope."""

    def permission_allowed(
        self, user: Any, permission_id: str, *, context: dict[str, Any] | None = None
    ) -> bool:
        """Return whether the current grants authorize the supplied scoped operation."""
        ...
