"""Fixed audience policy for verified synchronous sample ingestion credentials."""

from typing import Any


class SampleIngestPolicy:
    """Grant the existing synchronous sample-ingestion capability to a verified machine."""

    def __init__(self, principal_type: type[object]) -> None:
        """Bind the trusted credential adapter's identity type without importing its runtime.

        Args:
            principal_type: Host-owned marker class produced only after credential verification.
                This capability is never taken from request or manifest input.
        """
        self._principal_type = principal_type

    def permission_allowed(
        self, user: Any, permission_id: str, *, context: dict[str, Any] | None = None
    ) -> bool:
        """Reject unverified identities and permissions outside synchronous sample ingestion."""
        return isinstance(user, self._principal_type) and permission_id in {
            "internal.ingest:manage",
            "sample:edit:own",
        }

    def scope_allowed(self, user: Any, context: dict[str, Any] | None) -> bool:
        """Retain trusted-machine manifest access after deployment audience verification.

        The credential verifier checks the destination deployment. That token audience
        is distinct from the sample's clinical environment. Existing machine ingress
        does not use interactive account assay/environment assignments.
        """
        return isinstance(user, self._principal_type)
