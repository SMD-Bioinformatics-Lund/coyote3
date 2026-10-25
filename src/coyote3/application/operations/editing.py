"""Authorized editing sessions for registered document authoring workflows."""

from collections.abc import Callable
from typing import Any, Literal
from uuid import UUID, uuid4

from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.contracts.editing import EditLeaseStatus
from coyote3.domain.common.errors import api_error
from coyote3.domain.exceptions import AppError


class EditableResource:
    """Bind a resource's edit grant, authoritative loader and stable business key."""

    def __init__(
        self,
        permission: str,
        load: Callable[[str], dict[str, Any]],
        identity_field: str,
        *,
        sample_scoped: bool = False,
    ) -> None:
        """Bind an editor's authorization and canonical document lookup.

        Args:
            permission: Existing catalog grant required to open an editing session.
            load: Trusted reader resolving accepted identifiers to current documents.
            identity_field: Stable stored field shared by every alias/version of this resource.
            sample_scoped: Whether acquisition and renewal also check sample access scope.
        """
        self.permission = permission
        self.load = load
        self.identity_field = identity_field
        self.sample_scoped = sample_scoped


class DocumentEditors:
    """Keep lease lifecycle subject to the same grants and record protection as editing."""

    def __init__(self, runtime: ApplicationRuntime, resources: dict[str, EditableResource]) -> None:
        """Register trusted resource loaders; requests cannot introduce resource kinds.

        Args:
            runtime: Authenticated execution and shared lease persistence.
            resources: Fixed editor kinds, their grants and authoritative document readers.
        """
        self.runtime = runtime
        self.resources = resources

    def _resource(self, kind: str) -> EditableResource:
        """Resolve an allowlisted editor kind, rejecting arbitrary collection names."""
        resource = self.resources.get(kind)
        if resource is None:
            raise api_error(404, "Document editor not found")
        return resource

    def _identity(self, kind: str, identity: str) -> str:
        """Resolve aliases to one lock identity and reject protected system documents."""
        resource = self._resource(kind)
        doc = resource.load(identity)
        if not doc:
            raise api_error(404, "Document not found")
        if doc.get("system_installed") or doc.get("system_managed"):
            raise api_error(403, "System-installed documents cannot be edited")
        canonical = doc.get(resource.identity_field)
        if canonical is None:
            raise api_error(409, "Document has no stable editing identity")
        return str(canonical)

    def session(
        self,
        kind: str,
        identity: str,
        editor_id: UUID,
        action: Literal["acquire", "renew", "release"],
    ) -> EditLeaseStatus | None:
        """Acquire, renew or release a document lease under current edit permission.

        Args:
            kind: Registered editor kind, not a MongoDB collection name.
            identity: Business key or document identifier accepted by that editor.
            editor_id: Unique per-form session identifier; never an authentication credential.
            action: Lease operation; renewal cannot reclaim an expired session.

        Returns:
            Current ownership for acquisition/renewal, or None for release.

        Raises:
            AppError: Access is denied, the record is protected or the lease was lost.
        """
        resource = self._resource(kind)
        if action not in {"acquire", "renew", "release"}:
            raise api_error(422, "Unknown editing action")

        def execute(actor: Any, _sample: Any) -> EditLeaseStatus | None:
            """Resolve the document only after authorization and use verified ownership."""
            try:
                identity_key = self._identity(kind, identity)
            except AppError as error:
                if action == "release" and error.status_code == 404:
                    return None
                raise
            service = self.runtime.document_editing
            if service is None:
                raise api_error(503, "Document editing is unavailable")
            if action == "release":
                service.release(kind, identity_key, owner=actor.username, editor_id=editor_id)
                return None
            if action == "renew":
                return service.renew(kind, identity_key, owner=actor.username, editor_id=editor_id)
            return service.acquire(kind, identity_key, owner=actor.username, editor_id=editor_id)

        return self.runtime.execute(
            f"editing.{action}",
            (resource.permission,),
            execute,
            sample_id=identity if resource.sample_scoped else None,
        )

    def require_owner(
        self, kind: str, identity: str, actor: Any, session_required: bool
    ) -> Callable[[], None] | None:
        """Guard an authorized mutation, taking a temporary lease for immediate actions.

        Args:
            kind: Registered editor kind.
            identity: Record lookup identity, resolved to its stable key.
            actor: Identity already authenticated and authorized for this mutation.
            session_required: Whether a form session must already own the document.

        Returns:
            Cleanup for a temporary lease, or None for a retained interactive lease.

        Raises:
            AppError: Another editor owns the record or the interactive lease was lost.
        """
        service = self.runtime.document_editing
        if service is not None:
            canonical = self._identity(kind, identity)
            if not session_required:
                return service.hold_for_action(
                    kind,
                    canonical,
                    owner=actor.username,
                    editor_id=self.runtime.editor_id or uuid4(),
                )
            service.require_owner(
                kind,
                canonical,
                owner=actor.username,
                editor_id=self.runtime.editor_id,
            )
        return None
