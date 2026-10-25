"""Expiring ownership of a single document's interactive editing session."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID

from coyote3.contracts.editing import EditLeaseStatus
from coyote3.domain.common.errors import api_error
from coyote3.domain.editing import EditLeaseRepository


class DocumentEditing:
    """Coordinate editors across API workers without retaining login credentials."""

    lifetime = timedelta(seconds=90)

    def __init__(
        self, repository: EditLeaseRepository, *, clock: Callable[[], datetime] | None = None
    ) -> None:
        """Bind shared persistence and an optional UTC clock.

        Args:
            repository: Atomic ownership operations shared across API workers.
            clock: Current UTC time; None uses the system clock.
        """
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def key(resource_type: str, resource_id: str) -> str:
        """Encode a canonical resource pair without ambiguous delimiter collisions."""
        return f"{len(resource_type)}:{resource_type}{resource_id}"

    def acquire(
        self, resource_type: str, resource_id: str, *, owner: str, editor_id: UUID
    ) -> EditLeaseStatus:
        """Claim an available document or return the current editor's public identity.

        Args:
            resource_type: Authorized resource kind from the application's registry.
            resource_id: Canonical identity resolved from the authoritative document.
            owner: Verified username; never a caller-supplied ownership claim.
            editor_id: Unique identifier for this browser form or SDK editing session.

        Returns:
            Ownership and expiry, without exposing the competing session identifier.
        """
        now = self.clock()
        key = self.key(resource_type, resource_id)
        record = self.repository.acquire(
            key,
            owner=owner,
            editor_id=str(editor_id),
            now=now,
            expires_at=now + self.lifetime,
        )
        owned = record is not None
        record = record or self.repository.read(key, now=now) or {}
        return EditLeaseStatus(
            resource_type=resource_type,
            resource_id=resource_id,
            owned=owned,
            owner=record.get("owner"),
            expires_at=record.get("expires_at"),
        )

    def renew(
        self, resource_type: str, resource_id: str, *, owner: str, editor_id: UUID
    ) -> EditLeaseStatus:
        """Extend a live lease; never reacquire an expired or replaced editing session.

        Args:
            resource_type: Authorized resource kind.
            resource_id: Canonical document identity.
            owner: Verified username.
            editor_id: Session identifier returned to the caller's editor state.

        Returns:
            Renewed ownership and server expiry.

        Raises:
            AppError: Ownership expired or changed; the editor must reload before retrying.
        """
        now = self.clock()
        record = self.repository.renew(
            self.key(resource_type, resource_id),
            owner=owner,
            editor_id=str(editor_id),
            now=now,
            expires_at=now + self.lifetime,
        )
        if record is None:
            raise api_error(
                409,
                "Editing session expired or changed. Keep your unsaved text and reload "
                "the document before editing again.",
                category="edit_lease_lost",
            )
        return EditLeaseStatus(
            resource_type=resource_type,
            resource_id=resource_id,
            owned=True,
            owner=owner,
            expires_at=record["expires_at"],
        )

    def release(self, resource_type: str, resource_id: str, *, owner: str, editor_id: UUID) -> None:
        """Release only this editor's lease; repeated and stale releases are harmless.

        Args:
            resource_type: Registered editor kind.
            resource_id: Canonical document identity.
            owner: Verified username.
            editor_id: Unique form or SDK editing-session identifier.
        """
        self.repository.release(
            self.key(resource_type, resource_id), owner=owner, editor_id=str(editor_id)
        )

    def require_owner(
        self, resource_type: str, resource_id: str, *, owner: str, editor_id: UUID | None
    ) -> None:
        """Require and renew ownership before a document mutation.

        Args:
            resource_type: Authorized resource kind.
            resource_id: Canonical document identity.
            owner: Verified username.
            editor_id: Current session identifier; None is rejected.

        Raises:
            AppError: No session was supplied, or the session no longer owns the document.

        Notes:
            The lease complements the document's revision precondition. It does not replace
            a transactional or compare-and-set write against the expected revision.
        """
        if editor_id is None:
            raise api_error(
                409,
                "Open an editing session before changing this document.",
                category="edit_lease_required",
            )
        self.renew(resource_type, resource_id, owner=owner, editor_id=editor_id)

    def hold_for_action(
        self, resource_type: str, resource_id: str, *, owner: str, editor_id: UUID
    ) -> Callable[[], None] | None:
        """Hold a document during a revision-checked immediate action.

        Args:
            resource_type: Registered editor kind.
            resource_id: Canonical document identity.
            owner: Verified username.
            editor_id: Current form session, or a fresh identifier for this action.

        Returns:
            Cleanup for a newly acquired lease; None preserves an existing form's lease.

        Raises:
            AppError: A different editor currently owns the document.
        """
        existing = self.repository.read(self.key(resource_type, resource_id), now=self.clock())
        retained = bool(
            existing and existing["owner"] == owner and existing["editor_id"] == str(editor_id)
        )
        lease = self.acquire(resource_type, resource_id, owner=owner, editor_id=editor_id)
        if not lease.owned:
            raise api_error(
                409,
                f"{lease.owner or 'Another user'} is editing this document.",
                category="edit_lease_conflict",
            )
        if retained:
            return None
        return lambda: self.release(resource_type, resource_id, owner=owner, editor_id=editor_id)
