"""Authoritative administration use cases with current actor and permission enforcement."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import ExitStack
from typing import TYPE_CHECKING, Any

from coyote3.application.operations.runtime import ApplicationRuntime
from coyote3.contracts.admin import (
    AdminSampleUpdatePayload,
)
from coyote3.contracts.public import PublicAssayCatalogImportRequest as DraftImport
from coyote3.contracts.public import PublicAssayCatalogTransitionRequest as Transition
from coyote3.contracts.public import PublicAssayCatalogUpdateRequest as DraftUpdate
from coyote3.contracts.resource_fields import (
    AssayField,
    ConfigurationField,
    DiagnosisField,
    GeneListField,
    GroupField,
)
from coyote3.contracts.schemas.assay_groups import (
    AssayGroupCreate,
    AssayGroupStatus,
)
from coyote3.contracts.schemas.assay_setup import (
    AssaySetupAction,
    AssaySetupContent,
    AssaySetupUpdate,
)
from coyote3.contracts.schemas.diagnoses import (
    DiagnosisAssociationUpdate,
    DiagnosisCreate,
    DiagnosisUpdate,
    SharedDiagnosisCreate,
    SharedDiagnosisUpdate,
)

if TYPE_CHECKING:
    from coyote3.application.accounts.permissions import PermissionManagementService
    from coyote3.application.accounts.roles import RoleManagementService
    from coyote3.application.accounts.users import UserManagementService
    from coyote3.application.resources.asp import AspService
    from coyote3.application.resources.aspc import AspcService
    from coyote3.application.resources.assay_groups import AssayGroupService
    from coyote3.application.resources.assay_setup import AssaySetupService
    from coyote3.application.resources.diagnoses import DiagnosisService
    from coyote3.application.resources.fields import ResourceFieldService
    from coyote3.application.resources.isgl import IsglService
    from coyote3.application.resources.public_assay_catalog import (
        PublicAssayCatalogManagementService,
    )
    from coyote3.application.resources.sample import ResourceSampleService


class Users:
    """Authorized users operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], UserManagementService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def list_users(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the user list.

        Args:
            q: Case-insensitive search text; empty text selects all records.
            page: One-based result page.
            per_page: Maximum records per page.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (user:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.list_users",
            ("user:list",),
            lambda actor, sample: self._service().list_users_payload(
                q=q, page=page, per_page=per_page
            ),
        )

    def create_user_context(self) -> dict[str, Any]:
        """Return create-form context for a user.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (user:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.create_user_context",
            ("user:create",),
            lambda actor, sample: self._service().create_context_payload(
                actor_username=actor.username
            ),
        )

    def user_context(self, *, user_id: str) -> dict[str, Any]:
        """Return edit-form context for a user.

        Args:
            user_id: Registered account identifier.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (user:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.user_context",
            ("user:view",),
            lambda actor, sample: self._service().context_payload(user_id=user_id),
        )

    def create_user(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a user.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (user:create), validation
                or the operation's existing business rules reject the request.
        """
        permissions: tuple[str, ...] = ("user:create",)
        form = payload.get("form_data") or {}
        if isinstance(form, dict):
            if "roles" in form:
                permissions += ("user:role:edit",)
            if {"asp_ids", "asp_groups", "environments"} & form.keys():
                permissions += ("user:group:edit",)
        return self._runtime.execute(
            "users.create_user",
            permissions,
            lambda actor, sample: self._service().create_user(
                payload=payload,
                actor_username=actor.username,
                actor_is_superuser=actor.is_superuser,
            ),
        )

    def update_user(self, *, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a user.

        Args:
            user_id: Registered account identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (user:edit), validation
                or the operation's existing business rules reject the request.
        """
        permissions: tuple[str, ...] = ("user:edit",)
        form = payload.get("form_data") or {}
        if isinstance(form, dict):
            if "roles" in form:
                permissions += ("user:role:edit",)
            if {"asp_ids", "asp_groups", "environments"} & form.keys():
                permissions += ("user:group:edit",)
        return self._runtime.execute(
            "users.update_user",
            permissions,
            lambda actor, sample: self._service().update_user(
                user_id=user_id,
                payload=payload,
                actor_username=actor.username,
                actor_is_superuser=actor.is_superuser,
            ),
            edit_resource=("users", user_id),
        )

    def delete_user(self, *, user_id: str) -> dict[str, Any]:
        """Delete a user.

        Args:
            user_id: Registered account identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (user:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.delete_user",
            ("user:delete",),
            lambda actor, sample: self._service().delete_user(
                user_id=user_id, actor_is_superuser=actor.is_superuser
            ),
            edit_resource=("users", user_id),
            editing_session_required=False,
        )

    def toggle_user_status(self, *, user_id: str) -> dict[str, Any]:
        """Toggle a user's active status.

        Args:
            user_id: Registered account identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (user:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.toggle_user_status",
            ("user:edit",),
            lambda actor, sample: self._service().toggle_user(
                user_id=user_id, actor_is_superuser=actor.is_superuser
            ),
            edit_resource=("users", user_id),
            editing_session_required=False,
        )

    def invite_local_user(self, *, user_id: str) -> dict[str, Any]:
        """Issue a set-password invite link for local users.

        Args:
            user_id: Registered account identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (user:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "users.invite_local_user",
            ("user:edit",),
            lambda actor, sample: self._service().send_local_user_invite(
                user_id=user_id, actor_username=actor.username
            ),
        )

    def validate_username(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether a username is already in use.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (user:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "users.validate_username",
                ("user:create",),
                lambda actor, sample: self._service().username_exists(
                    username=str(payload.get("username", ""))
                ),
            )
        )

    def validate_email(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether an email address is already in use.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (user:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "users.validate_email",
                ("user:create",),
                lambda actor, sample: self._service().email_exists(
                    email=str(payload.get("email", ""))
                ),
            )
        )


class Roles:
    """Authorized roles operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], RoleManagementService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def list_roles(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the role list.

        Args:
            q: Case-insensitive search text; empty text selects all records.
            page: One-based result page.
            per_page: Maximum records per page.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (role:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.list_roles",
            ("role:list",),
            lambda actor, sample: self._service().list_roles_payload(
                q=q, page=page, per_page=per_page
            ),
        )

    def create_role_context(self) -> dict[str, Any]:
        """Return create-form context for a role.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (role:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.create_role_context",
            ("role:create",),
            lambda actor, sample: self._service().create_context_payload(
                actor_username=actor.username
            ),
        )

    def role_context(self, *, role_id: str) -> dict[str, Any]:
        """Return edit-form context for a role.

        Args:
            role_id: Registered role identifier.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (role:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.role_context",
            ("role:view",),
            lambda actor, sample: self._service().context_payload(role_id=role_id),
        )

    def create_role(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a role.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (role:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.create_role",
            ("role:create",),
            lambda actor, sample: self._service().create_role(
                payload=payload, actor_username=actor.username
            ),
        )

    def update_role(self, *, role_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a role.

        Args:
            role_id: Registered role identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (role:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.update_role",
            ("role:edit",),
            lambda actor, sample: self._service().update_role(
                role_id=role_id, payload=payload, actor_username=actor.username
            ),
            edit_resource=("roles", role_id),
        )

    def toggle_role_status(self, *, role_id: str) -> dict[str, Any]:
        """Toggle a role's active status.

        Args:
            role_id: Registered role identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (role:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.toggle_role_status",
            ("role:edit",),
            lambda actor, sample: self._service().toggle_role(role_id=role_id),
            edit_resource=("roles", role_id),
            editing_session_required=False,
        )

    def delete_role(self, *, role_id: str) -> dict[str, Any]:
        """Delete a role.

        Args:
            role_id: Registered role identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (role:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "roles.delete_role",
            ("role:delete",),
            lambda actor, sample: self._service().delete_role(role_id=role_id),
            edit_resource=("roles", role_id),
            editing_session_required=False,
        )

    def validate_role_id(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether a role_id already exists.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (role:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "roles.validate_role_id",
                ("role:create",),
                lambda actor, sample: self._service().role_exists(
                    role_id=str(payload.get("role_id", ""))
                ),
            )
        )


class Permissions:
    """Authorized permissions operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], PermissionManagementService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def create_permission(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a permission policy.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (permission.policy:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.create_permission",
            ("permission.policy:create",),
            lambda actor, sample: self._service().create_permission(
                payload=payload, actor_username=actor.username
            ),
        )

    def list_permissions(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the permission-policy list.

        Args:
            q: Case-insensitive search text; empty text selects all records.
            page: One-based result page.
            per_page: Maximum records per page.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (permission.policy:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.list_permissions",
            ("permission.policy:list",),
            lambda actor, sample: self._service().list_permissions_payload(
                q=q, page=page, per_page=per_page
            ),
        )

    def create_permission_context(self) -> dict[str, Any]:
        """Return create-form context for a permission policy.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (permission.policy:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.create_permission_context",
            ("permission.policy:create",),
            lambda actor, sample: self._service().create_context_payload(
                actor_username=actor.username
            ),
        )

    def permission_context(self, *, perm_id: str) -> dict[str, Any]:
        """Return edit-form context for a permission policy.

        Args:
            perm_id: Registered permission-policy identifier.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (permission.policy:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.permission_context",
            ("permission.policy:view",),
            lambda actor, sample: self._service().context_payload(permission_id=perm_id),
        )

    def update_permission(self, *, perm_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a permission policy.

        Args:
            perm_id: Registered permission-policy identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (permission.policy:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.update_permission",
            ("permission.policy:edit",),
            lambda actor, sample: self._service().update_permission(
                permission_id=perm_id, payload=payload, actor_username=actor.username
            ),
            edit_resource=("permissions", perm_id),
        )

    def toggle_permission_status(self, *, perm_id: str) -> dict[str, Any]:
        """Toggle a permission policy's active status.

        Args:
            perm_id: Registered permission-policy identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (permission.policy:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.toggle_permission_status",
            ("permission.policy:edit",),
            lambda actor, sample: self._service().toggle_permission(permission_id=perm_id),
            edit_resource=("permissions", perm_id),
            editing_session_required=False,
        )

    def delete_permission(self, *, perm_id: str) -> dict[str, Any]:
        """Delete a permission policy.

        Args:
            perm_id: Registered permission-policy identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (permission.policy:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "permissions.delete_permission",
            ("permission.policy:delete",),
            lambda actor, sample: self._service().delete_permission(permission_id=perm_id),
            edit_resource=("permissions", perm_id),
            editing_session_required=False,
        )

    def validate_permission_id(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether a permission_id already exists.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (permission.policy:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "permissions.validate_permission_id",
                ("permission.policy:create",),
                lambda actor, sample: self._service().permission_exists(
                    permission_id=str(payload.get("permission_id", ""))
                ),
            )
        )


class Assays:
    """Authorized assays operations shared by HTTP and local callers."""

    def __init__(self, runtime: ApplicationRuntime, service: Callable[[], AspService]) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def create_asp(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create an assay panel.

        Args:
            payload: Submitted assay-panel payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.create_asp",
            ("assay.panel:create",),
            lambda actor, sample: self._service().create(
                payload=payload, actor_username=actor.username
            ),
        )

    def list_asp(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the assay-panel list.

        Args:
            q: Case-insensitive text search across panel identifiers and metadata; blank text omits the search filter.
            page: One-based result page; defaults to 1.
            per_page: Page size from 1 to 200; defaults to 30.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.list_asp",
            ("assay.panel:list",),
            lambda actor, sample: self._service().list_payload(q=q, page=page, per_page=per_page),
        )

    def create_asp_context(self) -> dict[str, Any]:
        """Return create-form context for an assay panel.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.panel:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.create_asp_context",
            ("assay.panel:create",),
            lambda actor, sample: self._service().create_context_payload(
                actor_username=actor.username
            ),
        )

    def asp_context(self, *, assay_panel_id: str) -> dict[str, Any]:
        """Return edit-form context for an assay panel.

        Args:
            assay_panel_id: Assay-panel identifier to load.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.asp_context",
            ("assay.panel:view",),
            lambda actor, sample: self._service().context_payload(panel_id=assay_panel_id),
        )

    def update_asp(self, *, assay_panel_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update an assay panel.

        Args:
            assay_panel_id: Assay-panel identifier to update.
            payload: Submitted assay-panel payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.update_asp",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().update(
                panel_id=assay_panel_id, payload=payload, actor_username=actor.username
            ),
            edit_resource=("asp", assay_panel_id),
        )

    def toggle_asp(self, *, assay_panel_id: str) -> dict[str, Any]:
        """Toggle assay-panel active status.

        Args:
            assay_panel_id: Assay-panel identifier to toggle.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.toggle_asp",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().toggle(panel_id=assay_panel_id),
            edit_resource=("asp", assay_panel_id),
            editing_session_required=False,
        )

    def delete_asp(self, *, assay_panel_id: str) -> dict[str, Any]:
        """Delete an assay panel.

        Args:
            assay_panel_id: Assay-panel identifier to delete.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assays.delete_asp",
            ("assay.panel:delete",),
            lambda actor, sample: self._service().delete(panel_id=assay_panel_id),
            edit_resource=("asp", assay_panel_id),
            editing_session_required=False,
        )

    def validate_asp_id(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether an asp_id already exists.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (assay.panel:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "assays.validate_asp_id",
                ("assay.panel:create",),
                lambda actor, sample: self._service().panel_exists(
                    asp_id=str(payload.get("asp_id", ""))
                ),
            )
        )


class AssayGroups:
    """Authorized assay groups operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], AssayGroupService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def assay_group_impact(self, *, group_id: str) -> dict[str, Any]:
        """Inspect status and affected assays; requires assay.panel:view.

        Args:
            group_id: Registered biological assay-group identifier.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_groups.assay_group_impact",
            ("assay.panel:view",),
            lambda actor, sample: self._service().impact(group_id),
        )

    def change_assay_group_status(
        self, *, group_id: str, payload: AssayGroupStatus
    ) -> dict[str, Any]:
        """Confirm availability with a reason and current revision; requires assay.panel:edit.

        Args:
            group_id: Registered biological assay-group identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_groups.change_assay_group_status",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().change_status(
                group_id, payload, actor=actor.username
            ),
        )

    def list_assay_groups(self) -> dict[str, Any]:
        """List registered system and custom groups; requires assay.panel:view.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_groups.list_assay_groups",
            ("assay.panel:view",),
            lambda actor, sample: self._service().list_payload(),
        )

    def create_assay_group(self, *, payload: AssayGroupCreate) -> dict[str, Any]:
        """Register a custom assay group; requires assay.panel:edit and records an audit event.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_groups.create_assay_group",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().create(payload, actor=actor.username),
        )


class Diagnoses:
    """Authorized diagnoses operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], DiagnosisService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def create_shared_diagnosis(self, *, payload: SharedDiagnosisCreate) -> dict[str, Any]:
        """Create one shared definition and selected assay links; requires assay.panel:edit.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.create_shared_diagnosis",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().create_definition(payload, actor=actor.username),
        )

    def change_diagnosis_association_status(
        self, *, assay_panel_id: str, diagnosis_id: str, payload: DiagnosisAssociationUpdate
    ) -> dict[str, Any]:
        """Enable or disable only this assay link; requires assay.panel:edit.

        Args:
            assay_panel_id: Registered assay-panel identifier.
            diagnosis_id: Registered shared diagnosis identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.change_diagnosis_association_status",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().set_association_status(
                assay_panel_id, diagnosis_id, payload, actor=actor.username
            ),
        )

    def list_shared_diagnoses(self) -> dict[str, Any]:
        """List shared definitions; requires assay.panel:view.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.list_shared_diagnoses",
            ("assay.panel:view",),
            lambda actor, sample: self._service().definitions_payload(),
        )

    def revise_shared_diagnosis(
        self, *, diagnosis_id: str, payload: SharedDiagnosisUpdate
    ) -> dict[str, Any]:
        """Revise shared metadata for all associated assays; requires assay.panel:edit.

        Args:
            diagnosis_id: Registered shared diagnosis identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.revise_shared_diagnosis",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().revise_definition(
                diagnosis_id, payload, actor=actor.username
            ),
            edit_resource=("diagnoses", diagnosis_id),
        )

    def list_diagnoses(self, *, assay_panel_id: str) -> dict[str, Any]:
        """List current and retired diagnoses; requires assay.panel:view.

        Args:
            assay_panel_id: Registered assay-panel identifier.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.list_diagnoses",
            ("assay.panel:view",),
            lambda actor, sample: self._service().list_payload(assay_panel_id),
        )

    def create_diagnosis(self, *, assay_panel_id: str, payload: DiagnosisCreate) -> dict[str, Any]:
        """Register a diagnosis under an existing assay; requires assay.panel:edit.

        Args:
            assay_panel_id: Registered assay-panel identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.create_diagnosis",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().save(
                assay_panel_id, payload, actor=actor.username
            ),
        )

    def update_diagnosis(
        self, *, assay_panel_id: str, diagnosis_id: str, payload: DiagnosisUpdate
    ) -> dict[str, Any]:
        """Revise or retire a diagnosis; requires assay.panel:edit and its current version.

        Args:
            assay_panel_id: Registered assay-panel identifier.
            diagnosis_id: Registered shared diagnosis identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "diagnoses.update_diagnosis",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().save(
                assay_panel_id, payload, actor=actor.username, diagnosis_id=diagnosis_id
            ),
        )


class AssayConfigurations:
    """Authorized assay configurations operations shared by HTTP and local callers."""

    def __init__(self, runtime: ApplicationRuntime, service: Callable[[], AspcService]) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def list_aspc(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the assay-config list.

        Args:
            q: Case-insensitive text search across configuration identifiers and metadata; blank text omits the search filter.
            page: One-based result page; defaults to 1.
            per_page: Page size from 1 to 200; defaults to 30.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.config:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.list_aspc",
            ("assay.config:list",),
            lambda actor, sample: self._service().list_payload(q=q, page=page, per_page=per_page),
        )

    def create_aspc_context(self, *, category: str = "DNA") -> dict[str, Any]:
        """Return create-form context for an assay config.

        Args:
            category: Requested assay category.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.config:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.create_aspc_context",
            ("assay.config:create",),
            lambda actor, sample: self._service().create_context_payload(
                category=category, actor_username=actor.username
            ),
        )

    def aspc_context(self, *, assay_id: str) -> dict[str, Any]:
        """Return edit-form context for an assay config.

        Args:
            assay_id: Assay-config identifier to load.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.config:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.aspc_context",
            ("assay.config:view",),
            lambda actor, sample: self._service().context_payload(assay_id=assay_id),
        )

    def create_aspc(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create an assay config.

        Args:
            payload: Submitted assay-config payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.config:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.create_aspc",
            ("assay.config:create",),
            lambda actor, sample: self._service().create(
                payload=payload, actor_username=actor.username
            ),
        )

    def update_aspc(self, *, assay_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update an assay config.

        Args:
            assay_id: Assay-config identifier to update.
            payload: Submitted assay-config payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.config:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.update_aspc",
            ("assay.config:edit",),
            lambda actor, sample: self._service().update(
                assay_id=assay_id, payload=payload, actor_username=actor.username
            ),
            edit_resource=("aspc", assay_id),
        )

    def toggle_aspc(self, *, assay_id: str) -> dict[str, Any]:
        """Toggle assay-config active status.

        Args:
            assay_id: Assay-config identifier to toggle.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.config:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.toggle_aspc",
            ("assay.config:edit",),
            lambda actor, sample: self._service().toggle(assay_id=assay_id),
            edit_resource=("aspc", assay_id),
            editing_session_required=False,
        )

    def delete_aspc(self, *, assay_id: str) -> dict[str, Any]:
        """Delete an assay config.

        Args:
            assay_id: Assay-config identifier to delete.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.config:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_configurations.delete_aspc",
            ("assay.config:delete",),
            lambda actor, sample: self._service().delete(assay_id=assay_id),
            edit_resource=("aspc", assay_id),
            editing_session_required=False,
        )

    def validate_aspc_id(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether an aspc_id already exists.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (assay.config:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "assay_configurations.validate_aspc_id",
                ("assay.config:create",),
                lambda actor, sample: self._service().assay_config_exists(
                    aspc_id=str(payload.get("aspc_id", "") or ""),
                    asp_id=str(payload.get("asp_id", "") or ""),
                    diagnosis_id=str(payload.get("diagnosis_id", "") or ""),
                    environment=str(payload.get("environment", "") or ""),
                ),
            )
        )


class GeneLists:
    """Authorized gene lists operations shared by HTTP and local callers."""

    def __init__(self, runtime: ApplicationRuntime, service: Callable[[], IsglService]) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def create_genelist(self, *, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a genelist.

        Args:
            payload: Submitted genelist payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.create_genelist",
            ("gene_list.insilico:create",),
            lambda actor, sample: self._service().create(
                payload=payload, actor_username=actor.username
            ),
        )

    def list_genelists(self, *, q: str = "", page: int = 1, per_page: int = 30) -> dict[str, Any]:
        """Return the genelist list.

        Args:
            q: Case-insensitive text search across genelist identifiers and metadata; blank text omits the search filter.
            page: One-based result page; defaults to 1.
            per_page: Page size from 1 to 200; defaults to 30.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.list_genelists",
            ("gene_list.insilico:list",),
            lambda actor, sample: self._service().list_payload(q=q, page=page, per_page=per_page),
        )

    def create_genelist_context(self) -> dict[str, Any]:
        """Return create-form context for a genelist.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.create_genelist_context",
            ("gene_list.insilico:create",),
            lambda actor, sample: self._service().create_context_payload(
                actor_username=actor.username
            ),
        )

    def genelist_context(self, *, genelist_id: str) -> dict[str, Any]:
        """Return edit-form context for a genelist.

        Args:
            genelist_id: Genelist identifier to load.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.genelist_context",
            ("gene_list.insilico:view",),
            lambda actor, sample: self._service().context_payload(genelist_id=genelist_id),
        )

    def genelist_view_context(
        self, *, genelist_id: str, assay: str | None = None
    ) -> dict[str, Any]:
        """Return read-only context for a genelist.

        Args:
            genelist_id: Genelist identifier to load.
            assay: Optional assay used to filter visible genes.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.genelist_view_context",
            ("gene_list.insilico:view",),
            lambda actor, sample: self._service().view_context_payload(
                genelist_id=genelist_id, assay=assay
            ),
        )

    def update_genelist(self, *, genelist_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Update a genelist.

        Args:
            genelist_id: Genelist identifier to update.
            payload: Submitted genelist payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.update_genelist",
            ("gene_list.insilico:edit",),
            lambda actor, sample: self._service().update(
                genelist_id=genelist_id, payload=payload, actor_username=actor.username
            ),
            edit_resource=("genelists", genelist_id),
        )

    def toggle_genelist(self, *, genelist_id: str) -> dict[str, Any]:
        """Toggle genelist active status.

        Args:
            genelist_id: Genelist identifier to toggle.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.toggle_genelist",
            ("gene_list.insilico:edit",),
            lambda actor, sample: self._service().toggle(genelist_id=genelist_id),
            edit_resource=("genelists", genelist_id),
            editing_session_required=False,
        )

    def delete_genelist(self, *, genelist_id: str) -> dict[str, Any]:
        """Delete a genelist.

        Args:
            genelist_id: Genelist identifier to delete.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "gene_lists.delete_genelist",
            ("gene_list.insilico:delete",),
            lambda actor, sample: self._service().delete(genelist_id=genelist_id),
            edit_resource=("genelists", genelist_id),
            editing_session_required=False,
        )

    def validate_isgl_id(self, *, payload: dict[str, Any]) -> bool:
        """Validate whether an isgl_id already exists.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            True if the submitted identity is registered, otherwise False.

        Raises:
            AppError: Authentication, required grants (gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return bool(
            self._runtime.execute(
                "gene_lists.validate_isgl_id",
                ("gene_list.insilico:create",),
                lambda actor, sample: self._service().genelist_exists(
                    isgl_id=str(payload.get("isgl_id", ""))
                ),
            )
        )


class SampleAdministration:
    """Authorized sample administration operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], ResourceSampleService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def list_admin_samples(
        self,
        *,
        search: str = "",
        asp_group: str = "",
        asp_id: str = "",
        page: int = 1,
        per_page: int = 30,
    ) -> dict[str, Any]:
        """Return the sample list.

        Args:
            search: Free-text search string.
            asp_group: Assay group used to select active, accessible panels; blank text omits the group filter.
            asp_id: Assay-panel identifier used to narrow the active, accessible panels; blank text omits the panel filter.
            page: One-based result page; defaults to 1.
            per_page: Page size from 1 to 200; defaults to 30.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (sample:list:global), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "sample_administration.list_admin_samples",
            ("sample:list:global",),
            lambda actor, sample: self._service().list_payload(
                asp_ids=None if actor.is_superuser else actor.asp_ids,
                search=search,
                asp_group=asp_group,
                asp_id=asp_id,
                page=page,
                per_page=per_page,
            ),
        )

    def admin_sample_context(self, *, sample_id: str) -> dict[str, Any]:
        """Return edit context for an sample.

        Args:
            sample_id: Sample identifier to load.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (sample:view:global), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "sample_administration.admin_sample_context",
            ("sample:view:global",),
            lambda actor, sample: self._service().context_payload(sample_id=sample_id),
        )

    def update_sample(self, *, sample_id: str, payload: AdminSampleUpdatePayload) -> dict[str, Any]:
        """Update an sample.

        Args:
            sample_id: Sample identifier to update.
            payload: Submitted sample payload.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (sample:edit:global), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "sample_administration.update_sample",
            ("sample:edit:global",),
            lambda actor, sample: self._service().update(
                sample_id=sample_id, payload=payload.model_dump(), actor_username=actor.username
            ),
            edit_resource=("samples", sample_id),
        )

    def delete_sample(self, *, sample_id: str) -> dict[str, Any]:
        """Delete owned sample records and queue generated report files for permanent erasure.

        Args:
            sample_id: Sample identifier to delete.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (sample:delete:global), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "sample_administration.delete_sample",
            ("sample:delete:global",),
            lambda actor, sample: self._service().delete(sample_id=sample_id),
            edit_resource=("samples", sample_id),
            editing_session_required=False,
        )


class AssaySetups:
    """Authorized assay setups operations shared by HTTP and local callers."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], AssaySetupService]
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def delete_setup(self, *, identifier: str, revision: int) -> dict[str, Any]:
        """Delete an unchanged draft or submitted setup; requires assay.panel:delete.

        Args:
            identifier: Saved setup or catalog-version identifier.
            revision: Expected saved revision; concurrent changes are rejected.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:delete), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.delete_setup",
            ("assay.panel:delete",),
            lambda actor, sample: self._service().delete_unpublished(
                identifier, revision, actor=actor.username
            ),
            edit_resource=("assay-setups", identifier),
            editing_session_required=False,
        )

    def list_setups(self) -> dict[str, Any]:
        """List saved setup summaries; requires assay.panel:list.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:list), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.list_setups",
            ("assay.panel:list",),
            lambda actor, sample: self._service().list_payload(),
        )

    def new_setup_context(self) -> dict[str, Any]:
        """Return the assay form and optional scope choices for a new setup.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.panel:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.new_setup_context",
            ("assay.panel:create",),
            lambda actor, sample: self._service().context(None, actor=actor.username),
        )

    def setup_context(self, *, identifier: str) -> dict[str, Any]:
        """Inspect staged configuration, readiness and revision history without writing data.

        Args:
            identifier: Saved setup or catalog-version identifier.

        Returns:
            Form definitions, current values and permitted choices for the requested resource.

        Raises:
            AppError: Authentication, required grants (assay.panel:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.setup_context",
            ("assay.panel:view",),
            lambda actor, sample: self._service().context(identifier, actor=actor.username),
        )

    def create_setup(self, *, payload: AssaySetupContent) -> dict[str, Any]:
        """Reserve an assay identifier and save a draft without creating an active ASP.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:create, assay.panel:create, assay.config:create, gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.create_setup",
            ("assay.panel:create", "assay.config:create", "gene_list.insilico:create")
            + (("gene_list.insilico:edit",) if payload.existing_gene_list_ids else ()),
            lambda actor, sample: self._service().save(payload, actor=actor.username),
        )

    def save_setup(self, *, identifier: str, payload: AssaySetupUpdate) -> dict[str, Any]:
        """Save the current draft revision; submitted and published setups are immutable.

        Args:
            identifier: Saved setup or catalog-version identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit, assay.panel:create, assay.config:create, gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.save_setup",
            (
                "assay.panel:edit",
                "assay.panel:create",
                "assay.config:create",
                "gene_list.insilico:create",
            )
            + (("gene_list.insilico:edit",) if payload.content.existing_gene_list_ids else ()),
            lambda actor, sample: self._service().save(
                payload.content,
                identifier=identifier,
                revision=payload.revision,
                actor=actor.username,
            ),
            edit_resource=("assay-setups", identifier),
        )

    def submit_setup(self, *, identifier: str, payload: AssaySetupAction) -> dict[str, Any]:
        """Validate every selected scope/environment and freeze the setup for review.

        Args:
            identifier: Saved setup or catalog-version identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit, assay.panel:create, assay.config:create, gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.submit_setup",
            (
                "assay.panel:edit",
                "assay.panel:create",
                "assay.config:create",
                "gene_list.insilico:create",
            ),
            lambda actor, sample: self._service().transition(
                identifier, payload.revision, "submit", actor=actor.username
            ),
            edit_resource=("assay-setups", identifier),
            editing_session_required=False,
        )

    def publish_setup(self, *, identifier: str, payload: AssaySetupAction) -> dict[str, Any]:
        """Independently approve and atomically activate a complete submitted setup.

        Args:
            identifier: Saved setup or catalog-version identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit, assay.panel:create, assay.config:create, gene_list.insilico:create), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.publish_setup",
            (
                "assay.panel:edit",
                "assay.panel:create",
                "assay.config:create",
                "gene_list.insilico:create",
            ),
            lambda actor, sample: self._publish_with_gene_list_access(identifier, payload),
            edit_resource=("assay-setups", identifier),
            editing_session_required=False,
        )

    def _publish_with_gene_list_access(
        self, identifier: str, payload: AssaySetupAction
    ) -> dict[str, Any]:
        """Require gene-list edit permission when activation links shared lists.

        Args:
            identifier: Submitted setup identity, checked by the outer operation.
            payload: Expected revision and review notes.

        Returns:
            Published setup after atomic activation.

        Raises:
            AppError: The actor lacks edit permission or publication validation fails.
        """
        service = self._service()
        document = service.get(identifier)
        permissions = (
            ("gene_list.insilico:edit",)
            if document["content"].get("existing_gene_list_ids")
            else None
        )

        def publish(actor: Any, _sample: Any) -> dict[str, Any]:
            """Hold shared gene-list leases while applying their assay associations."""
            with ExitStack() as leases:
                if self._runtime.edit_guard is not None:
                    for gene_list_id in sorted(
                        document["content"].get("existing_gene_list_ids") or []
                    ):
                        release = self._runtime.edit_guard("genelists", gene_list_id, actor, False)
                        if release is not None:
                            leases.callback(release)
                return dict(
                    service.transition(
                        identifier,
                        payload.revision,
                        "publish",
                        actor=actor.username,
                        reason=payload.reason,
                    )
                )

        return self._runtime.execute(
            "assay_setups.activate_associations",
            permissions,
            publish,
        )

    def return_setup(self, *, identifier: str, payload: AssaySetupAction) -> dict[str, Any]:
        """Return a submitted setup to draft with an independent reviewer's explanation.

        Args:
            identifier: Saved setup or catalog-version identifier.
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (assay.panel:edit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "assay_setups.return_setup",
            ("assay.panel:edit",),
            lambda actor, sample: self._service().transition(
                identifier, payload.revision, "return", actor=actor.username, reason=payload.reason
            ),
            edit_resource=("assay-setups", identifier),
            editing_session_required=False,
        )


class CatalogAuthoring:
    """Authorized catalog authoring operations shared by HTTP and local callers."""

    def __init__(
        self,
        runtime: ApplicationRuntime,
        service: Callable[[], PublicAssayCatalogManagementService],
    ) -> None:
        """Bind current-identity authorization and the host-owned service factory.

        Args:
            runtime: Trusted authentication, current grants and audit capabilities.
            service: Lazy operation implementation with injected repositories.
        """
        self._runtime, self._service = runtime, service

    def delete_version(self, *, identifier: str, revision: int) -> dict[str, Any]:
        """Delete an unchanged unpublished version; requires catalog:draft.

        Args:
            identifier: Saved setup or catalog-version identifier.
            revision: Expected saved revision; concurrent changes are rejected.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:draft), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.delete_version",
            ("catalog:draft",),
            lambda actor, sample: self._service().delete_unpublished(
                identifier, revision, actor=actor.username
            ),
            edit_resource=("assay-catalog", identifier),
            editing_session_required=False,
        )

    def workspace(self) -> dict[str, Any]:
        """Read the catalog authoring workspace; requires `catalog:view`.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.workspace",
            ("catalog:view",),
            lambda actor, sample: self._service().workspace(),
        )

    def version(self, *, oid: str) -> dict[str, Any]:
        """Read one catalog version; requires `catalog:view`.

        Args:
            oid: Catalog version document identifier.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.version",
            ("catalog:view",),
            lambda actor, sample: self._service().document(oid),
        )

    def revisions(self, *, oid: str) -> dict[str, Any]:
        """Read a catalog version's revision history; requires `catalog:view`.

        Args:
            oid: Catalog version document identifier.

        Returns:
            Requested resource records and the existing catalog or revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.revisions",
            ("catalog:view",),
            lambda actor, sample: self._service().revisions(oid),
        )

    def preview_offerings(self, *, payload: DraftImport) -> dict[str, Any]:
        """Preview public services from validated sources without publishing; requires catalog:view.

        Args:
            payload: Authored fields validated against the managed resource contract.

        Returns:
            Validated preview content without saving or publishing a revision.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.preview_offerings",
            ("catalog:view",),
            lambda actor, sample: self._service().preview_offerings(
                payload.document, actor=actor.username
            ),
        )

    def preview(
        self,
        *,
        payload: DraftImport,
        mod: str | None = None,
        cat: str | None = None,
        isgl_key: str | None = None,
    ) -> dict[str, Any]:
        """Render supplied catalog content without saving it; requires `catalog:view`.

        Args:
            payload: Catalog document to validate and render.
            mod: Optional modality selection; None leaves it unselected.
            cat: Optional category selection within the modality.
            isgl_key: Optional gene-list selection for the category.

        Returns:
            Validated preview content without saving or publishing a revision.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.preview",
            ("catalog:view",),
            lambda actor, sample: self._service().preview(
                payload.document, actor=actor.username, mod=mod, cat=cat, isgl_key=isgl_key
            ),
        )

    def preview_matrix(
        self, *, payload: DraftImport, page: int = 1, per_page: int = 100, gene: str | None = None
    ) -> dict[str, Any]:
        """Preview a catalog's gene matrix without saving it; requires `catalog:view`.

        Args:
            payload: Catalog document to validate and render.
            page: One-based matrix page; defaults to 1.
            per_page: Rows per page from 1 to 500; defaults to 100.
            gene: Optional gene search text; None omits gene filtering.

        Returns:
            Validated preview content without saving or publishing a revision.

        Raises:
            AppError: Authentication, required grants (catalog:view), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.preview_matrix",
            ("catalog:view",),
            lambda actor, sample: self._service().preview_matrix(
                payload.document, actor=actor.username, page=page, per_page=per_page, gene=gene
            ),
        )

    def create(self) -> dict[str, Any]:
        """Create a catalog draft from current content; requires `catalog:draft`.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:draft), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.create",
            ("catalog:draft",),
            lambda actor, sample: self._service().create(actor=actor.username),
        )

    def import_draft(self, *, payload: DraftImport) -> dict[str, Any]:
        """Import catalog content as a new draft; requires `catalog:draft`.

        Args:
            payload: Full catalog document or supported modality export envelope.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:draft), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.import_draft",
            ("catalog:draft",),
            lambda actor, sample: self._service().create(
                actor=actor.username, imported=payload.document
            ),
        )

    def update(self, *, oid: str, payload: DraftUpdate) -> dict[str, Any]:
        """Replace draft catalog content at a revision; requires `catalog:draft`.

        Args:
            oid: Draft version document identifier.
            payload: Expected revision and replacement catalog content.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:draft), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.update",
            ("catalog:draft",),
            lambda actor, sample: self._service().update(
                oid, payload.revision, payload.catalog, actor=actor.username
            ),
            edit_resource=("assay-catalog", oid),
        )

    def submit(self, *, oid: str, payload: Transition) -> dict[str, Any]:
        """Submit a catalog draft to an independent reviewer; requires `catalog:submit`.

        Args:
            oid: Draft version document identifier.
            payload: Expected revision and reviewer username in assignee.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:submit), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.submit",
            ("catalog:submit",),
            lambda actor, sample: self._service().submit(
                oid, payload.revision, payload.assignee, actor=actor.username
            ),
            edit_resource=("assay-catalog", oid),
            editing_session_required=False,
        )

    def review(self, *, oid: str, payload: Transition) -> dict[str, Any]:
        """Approve or reject an assigned catalog review; requires `catalog:review`.

        Args:
            oid: Submitted catalog version document identifier.
            payload: Expected revision, approval flag, reason, and publisher assignee.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:review), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.review",
            ("catalog:review",),
            lambda actor, sample: self._service().decide(
                oid,
                payload.revision,
                actor=actor.username,
                approve=payload.approve,
                publisher=payload.assignee,
                reason=payload.reason,
            ),
            edit_resource=("assay-catalog", oid),
            editing_session_required=False,
        )

    def publish(self, *, oid: str, payload: Transition) -> dict[str, Any]:
        """Publish an approved catalog version; requires `catalog:publish`.

        Args:
            oid: Approved catalog version document identifier.
            payload: Expected revision; other transition fields are not used here.

        Returns:
            Mutation outcome with the affected resource identity and available revision metadata.

        Raises:
            AppError: Authentication, required grants (catalog:publish), validation
                or the operation's existing business rules reject the request.
        """
        return self._runtime.execute(
            "catalog_authoring.publish",
            ("catalog:publish",),
            lambda actor, sample: self._service().publish(
                oid, payload.revision, actor=actor.username
            ),
            edit_resource=("assay-catalog", oid),
            editing_session_required=False,
        )


class ReferenceData:
    """Authorized field and metadata reads for managed reference resources."""

    def __init__(
        self, runtime: ApplicationRuntime, service: Callable[[], ResourceFieldService]
    ) -> None:
        """Bind the current authorization runtime and reference-field implementation."""
        self._runtime, self._service = runtime, service

    def group_metadata(self, group_id: str) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            group_id: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.group_metadata",
            ("assay.panel:view",),
            lambda actor, sample: self._service().group_metadata(group_id),
        )

    def diagnosis_metadata(self, diagnosis_id: str) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            diagnosis_id: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.diagnosis_metadata",
            ("assay.panel:view",),
            lambda actor, sample: self._service().diagnosis_metadata(diagnosis_id),
        )

    def group_field(self, group_id: str, field: GroupField) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            group_id: Typed reference identifier or permitted field selection.
            field: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.group_field",
            ("assay.panel:view",),
            lambda actor, sample: self._service().group_field(group_id, field),
        )

    def diagnosis_field(self, diagnosis_id: str, field: DiagnosisField) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            diagnosis_id: Typed reference identifier or permitted field selection.
            field: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.diagnosis_field",
            ("assay.panel:view",),
            lambda actor, sample: self._service().diagnosis_field(diagnosis_id, field),
        )

    def assay_metadata(self, assay_panel_id: str) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            assay_panel_id: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.assay_metadata",
            ("assay.panel:view",),
            lambda actor, sample: self._service().assay_metadata(assay_panel_id),
        )

    def assay_field(self, assay_panel_id: str, field: AssayField) -> Any:
        """Read selected reference data after checking assay.panel:view.

        Args:
            assay_panel_id: Typed reference identifier or permitted field selection.
            field: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.assay_field",
            ("assay.panel:view",),
            lambda actor, sample: self._service().assay_field(assay_panel_id, field),
        )

    def configuration_metadata(self, aspc_id: str) -> Any:
        """Read selected reference data after checking assay.config:view.

        Args:
            aspc_id: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.configuration_metadata",
            ("assay.config:view",),
            lambda actor, sample: self._service().configuration_metadata(aspc_id),
        )

    def configuration_field(self, aspc_id: str, field: ConfigurationField) -> Any:
        """Read selected reference data after checking assay.config:view.

        Args:
            aspc_id: Typed reference identifier or permitted field selection.
            field: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.configuration_field",
            ("assay.config:view",),
            lambda actor, sample: self._service().configuration_field(aspc_id, field),
        )

    def gene_list_metadata(self, genelist_id: str) -> Any:
        """Read selected reference data after checking gene_list.insilico:view.

        Args:
            genelist_id: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.gene_list_metadata",
            ("gene_list.insilico:view",),
            lambda actor, sample: self._service().gene_list_metadata(genelist_id),
        )

    def gene_list_field(self, genelist_id: str, field: GeneListField) -> Any:
        """Read selected reference data after checking gene_list.insilico:view.

        Args:
            genelist_id: Typed reference identifier or permitted field selection.
            field: Typed reference identifier or permitted field selection.

        Returns:
            Permitted reference metadata or field value.

        Raises:
            AppError: Authentication, permission, lookup or field validation fails.
        """
        return self._runtime.execute(
            "reference_data.gene_list_field",
            ("gene_list.insilico:view",),
            lambda actor, sample: self._service().gene_list_field(genelist_id, field),
        )


class AdministrationServices:
    """Host-owned factories for account and managed-resource implementations."""

    def __init__(
        self,
        *,
        users: Callable[[], UserManagementService],
        roles: Callable[[], RoleManagementService],
        permissions: Callable[[], PermissionManagementService],
        assays: Callable[[], AspService],
        assay_groups: Callable[[], AssayGroupService],
        diagnoses: Callable[[], DiagnosisService],
        assay_configurations: Callable[[], AspcService],
        gene_lists: Callable[[], IsglService],
        sample_administration: Callable[[], ResourceSampleService],
        assay_setups: Callable[[], AssaySetupService],
        catalog_authoring: Callable[[], PublicAssayCatalogManagementService],
        reference_data: Callable[[], ResourceFieldService],
    ) -> None:
        """Bind administrative implementations without exposing repositories to callers.

        Args:
            users: Account lifecycle, safe forms and assignment validation.
            roles: Registered role and permission-assignment workflows.
            permissions: Permission-policy definitions and lifecycle workflows.
            assays: Assay-panel configuration and lifecycle workflows.
            assay_groups: Biological group registration and availability changes.
            diagnoses: Shared diagnosis definitions and assay associations.
            assay_configurations: Scope-bound assay configuration authoring.
            gene_lists: Managed gene-list authoring and inspection.
            sample_administration: Privileged sample editing and deletion workflows.
            assay_setups: Draft-first setup validation and independent publication.
            catalog_authoring: Catalog previews, revisions, assignment and publication.
            reference_data: Permitted fields and metadata for managed reference resources.
        """
        self.users = users
        self.roles = roles
        self.permissions = permissions
        self.assays = assays
        self.assay_groups = assay_groups
        self.diagnoses = diagnoses
        self.assay_configurations = assay_configurations
        self.gene_lists = gene_lists
        self.sample_administration = sample_administration
        self.assay_setups = assay_setups
        self.catalog_authoring = catalog_authoring
        self.reference_data = reference_data
