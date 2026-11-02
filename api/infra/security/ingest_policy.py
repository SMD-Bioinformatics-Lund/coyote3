"""Fixed audience policy for verified synchronous sample ingestion credentials."""

from typing import Any

from api.security.policy import AccessContext, PrincipalScope


class SampleIngestPolicy:
    """Grant the existing synchronous sample-ingestion capability to a verified machine."""

    def __init__(
        self, principal_type: type[object], *, scoped_principal_type: type[object] | None = None
    ) -> None:
        """Bind the trusted credential adapter's identity type without importing its runtime.

        Args:
            principal_type: Host-owned marker class produced only after credential verification.
                This capability is never taken from request or manifest input.
            scoped_principal_type: Managed credential marker requiring explicit assay/environment
                assignments; None retains the existing fixed-audience machine behavior.
        """
        self._principal_type = principal_type
        self._scoped_principal_type = scoped_principal_type

    def permission_allowed(
        self, user: Any, permission_id: str, *, context: dict[str, Any] | None = None
    ) -> bool:
        """Reject unverified identities and permissions outside synchronous sample ingestion."""
        managed = self._scoped_principal_type is not None and isinstance(
            user, self._scoped_principal_type
        )
        if managed:
            return (
                permission_id in {"internal.ingest:manage", "sample:edit:own", "internal.task:view"}
                and permission_id in user.permissions
                and self.scope_allowed(user, context)
                and (
                    not user.personal_token
                    or bool(
                        user.personal_permission_check
                        and user.personal_permission_check(permission_id, context)
                    )
                )
            )
        trusted = isinstance(user, self._principal_type) or (
            self._scoped_principal_type is not None
            and isinstance(user, self._scoped_principal_type)
        )
        return (
            trusted
            and self.scope_allowed(user, context)
            and permission_id
            in {
                "internal.ingest:manage",
                "sample:edit:own",
            }
        )

    def scope_allowed(self, user: Any, context: dict[str, Any] | None) -> bool:
        """Apply explicit managed-token scopes while preserving fixed-machine audiences.

        Args:
            user: Verified fixed-audience machine or managed service-token principal.
            context: Authoritative manifest assay/environment; None performs a preflight check.

        Returns:
            True for a fixed-audience machine or when every supplied managed scope matches.
            Destination deployment verification is separate from clinical environment selection.
        """
        if self._scoped_principal_type is not None and isinstance(
            user, self._scoped_principal_type
        ):
            required = AccessContext.from_mapping(context)
            granted = PrincipalScope.from_user(user)
            return (
                (not required.asp_id or required.asp_id in granted.asp_ids)
                and (not required.environment or required.environment in granted.environments)
                and (
                    not user.personal_token
                    or bool(
                        user.personal_permission_check
                        and user.personal_permission_check(None, context)
                    )
                )
            )
        return isinstance(user, self._principal_type)
