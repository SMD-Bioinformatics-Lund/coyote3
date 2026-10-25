"""Authenticated execution boundary for local application SDK operations."""

from collections.abc import Callable
from copy import deepcopy
from typing import Any, TypeVar, cast
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict

from coyote3.application.common.access import ScopePolicy, enforce_access, sample_scope_allowed
from coyote3.application.common.execution_context import (
    reset_current_request_id,
    reset_current_user,
    set_current_request_id,
    set_current_user,
)
from coyote3.application.editing import DocumentEditing
from coyote3.domain.common.errors import api_error
from coyote3.domain.exceptions import AppError

Result = TypeVar("Result")


class AccessEvent(BaseModel):
    """Credential-free authorization decision emitted before application execution."""

    model_config = ConfigDict(frozen=True)

    operation: str
    actor: Any | None
    permissions: tuple[str, ...]
    sample_id: str | None
    correlation_id: str
    allowed: bool


class ApplicationRuntime:
    """Trusted composition ports; callers cannot supply identity through operation inputs.

    Authentication must reload the identity for each call. The permission factory
    must resolve current grants. These ports are capabilities held by the host,
    not values accepted from an HTTP request or an untrusted Python script.
    """

    def __init__(
        self,
        *,
        authenticate: Callable[[], Any | None],
        policy_factory: Callable[[Any], ScopePolicy],
        sample_loader: Callable[[str], dict[str, Any] | None],
        assay_loader: Callable[[str], dict[str, Any] | None],
        audit_access: Callable[[AccessEvent], None],
        correlation_id: str | None = None,
        project_result: Callable[[Any], Any] = deepcopy,
        allowed_operations: frozenset[str] | None = None,
        document_editing: DocumentEditing | None = None,
        editor_id: UUID | None = None,
    ) -> None:
        """Bind trusted authentication, authorization, storage and audit capabilities.

        Args:
            authenticate: Reloads a verified identity or returns None for invalid credentials.
            policy_factory: Builds current role and attribute checks for the verified identity.
            sample_loader: Resolves authoritative sample attributes by name or identifier.
            assay_loader: Resolves assay group membership for sample scope checks.
            audit_access: Durably records decisions; a failure prevents execution.
            correlation_id: Host correlation identity; None allocates one per operation.
            project_result: Copies completed results into caller values while preserving
                model types; the adapter may normalize provider identifiers. It never
                transforms authoritative inputs before integrity checks.
            allowed_operations: Optional host-imposed audience restriction. None permits
                all declared operations subject to current grants; a fixed set limits
                machine credentials to their designated application operations.
            document_editing: Shared lease persistence; None is for isolated service tests.
            editor_id: Per-form editing session, distinct from authenticated identity.
        """
        self.authenticate = authenticate
        self.policy_factory = policy_factory
        self.sample_loader = sample_loader
        self.assay_loader = assay_loader
        self.audit_access = audit_access
        self.correlation_id = correlation_id
        self.project_result = project_result
        self.allowed_operations = allowed_operations
        self.document_editing = document_editing
        self.editor_id = editor_id
        self.edit_guard: Callable[[str, str, Any, bool], Callable[[], None] | None] | None = None

    def execute(
        self,
        operation: str,
        permissions: tuple[str, ...] | None,
        action: Callable[[Any, dict[str, Any] | None], Result],
        *,
        sample_id: str | None = None,
        sample_permissions: Callable[[dict[str, Any]], tuple[str, ...]] | None = None,
        edit_resource: tuple[str, str] | None = None,
        editing_session_required: bool = True,
    ) -> Result:
        """Authenticate, authorize, bind context and invoke one trusted operation.

        Args:
            operation: Stable application operation name for access auditing.
            permissions: Every required catalog permission. None explicitly selects an
                authenticated recipient-scoped operation with no catalog grant; an empty
                tuple is invalid so omitted permission declarations fail closed.
            action: Trusted service invocation supplied by the SDK implementation.
            sample_id: Sample to reload and authorize, or None for a global operation.
            sample_permissions: Trusted resolver for additional grants on the loaded sample,
                such as production publication; None adds no conditional grants.
            edit_resource: Canonical resource kind and lookup identity for an edited record.
            editing_session_required: False for an immediate lifecycle action that takes
                a temporary lease; True requires an already-open interactive editor.

        Returns:
            The service result, after execution under the authenticated actor.

        Raises:
            AppError: Authentication, password-change policy or access checks fail.
            ValueError: A composition error omitted the permission requirement.
            Exception: Audit delivery or the underlying service fails. The existing
                service owns business transactions and optimistic concurrency.
        """
        if permissions == ():
            raise ValueError("An application operation requires explicit permissions")
        permissions = permissions or ()
        correlation_id = self.correlation_id or str(uuid4())
        actor = None
        sample = None
        try:
            actor = self.authenticate()
            if actor is None:
                raise api_error(401, "Login required", category="auth")
            if self.allowed_operations is not None and operation not in self.allowed_operations:
                raise api_error(
                    403, "Credential is outside this operation's audience", category="scope"
                )
            if (
                getattr(actor, "must_change_password", False)
                and operation != "account.change_password"
            ):
                raise api_error(403, "Password change required", category="auth")
            for permission in permissions:
                enforce_access(actor, permission=permission, policy_factory=self.policy_factory)
            if sample_id is not None:
                sample = self.sample_loader(sample_id)
                if not sample:
                    raise api_error(404, "Sample not found", category="not_found")
                if not sample_scope_allowed(
                    actor,
                    sample,
                    policy_factory=self.policy_factory,
                    assay_loader=self.assay_loader,
                ):
                    raise api_error(403, "Sample is outside your access scope", category="scope")
                sample = deepcopy(sample)
                if sample_permissions is not None:
                    additional_permissions = sample_permissions(sample)
                    permissions += additional_permissions
                    for permission in additional_permissions:
                        enforce_access(
                            actor, permission=permission, policy_factory=self.policy_factory
                        )
        except AppError:
            self.audit_access(
                AccessEvent(
                    operation=operation,
                    actor=actor,
                    permissions=permissions,
                    sample_id=sample_id,
                    correlation_id=correlation_id,
                    allowed=False,
                )
            )
            raise
        user_token = set_current_user(actor)
        request_token = set_current_request_id(correlation_id)
        try:
            self.audit_access(
                AccessEvent(
                    operation=operation,
                    actor=actor,
                    permissions=permissions,
                    sample_id=sample_id,
                    correlation_id=correlation_id,
                    allowed=True,
                )
            )
            release = None
            if (
                edit_resource is not None
                and self.document_editing is not None
                and self.edit_guard is None
            ):
                raise api_error(503, "Document editing is not configured")
            if edit_resource is not None and self.edit_guard is not None:
                release = self.edit_guard(*edit_resource, actor, editing_session_required)
            try:
                return cast(Result, self.project_result(action(actor, sample)))
            finally:
                if release is not None:
                    release()
        finally:
            reset_current_request_id(request_token)
            reset_current_user(user_token)
