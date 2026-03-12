"""Admin-facing repository adapters with explicit methods."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.extensions import store, util
from api.infra.repositories.admin_sample_mongo import (
    MongoAdminSampleDeletionRepository as AdminSampleDeletionRepository,
)


class AdminRepository:
    """Repository facade for admin routes and services.

    The repository exposes explicit operations for user/role management while
    keeping legacy handler access available for still-migrating admin resources.
    """

    @property
    def permissions_handler(self):
        """Handle permissions handler.

        Returns:
            The function result.
        """
        return store.permissions_handler

    @property
    def roles_handler(self):
        """Handle roles handler.

        Returns:
            The function result.
        """
        return store.roles_handler

    @property
    def asp_handler(self):
        """Handle asp handler.

        Returns:
            The function result.
        """
        return store.asp_handler

    @property
    def schema_handler(self):
        """Handle schema handler.

        Returns:
            The function result.
        """
        return store.schema_handler

    @property
    def user_handler(self):
        """Handle user handler.

        Returns:
            The function result.
        """
        return store.user_handler

    @property
    def isgl_handler(self):
        """Handle isgl handler.

        Returns:
            The function result.
        """
        return store.isgl_handler

    @property
    def aspc_handler(self):
        """Handle aspc handler.

        Returns:
            The function result.
        """
        return store.aspc_handler

    @property
    def sample_handler(self):
        """Handle sample handler.

        Returns:
            The function result.
        """
        return store.sample_handler

    def list_users(self) -> list[dict[str, Any]]:
        """List users.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return [dict(item) for item in (self.user_handler.get_all_users() or []) if isinstance(item, dict)]

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        """Return user.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return self.user_handler.user_with_id(user_id)

    def create_user(self, user_data: dict[str, Any]) -> None:
        """Create user.

        Args:
            user_data (dict[str, Any]): Value for ``user_data``.

        Returns:
            None.
        """
        self.user_handler.create_user(user_data)

    def update_user(self, user_id: str, user_data: dict[str, Any]) -> None:
        """Update user.

        Args:
            user_id (str): Value for ``user_id``.
            user_data (dict[str, Any]): Value for ``user_data``.

        Returns:
            None.
        """
        self.user_handler.update_user(user_id, user_data)

    def delete_user(self, user_id: str) -> None:
        """Delete user.

        Args:
            user_id (str): Value for ``user_id``.

        Returns:
            None.
        """
        self.user_handler.delete_user(user_id)

    def set_user_active(self, user_id: str, is_active: bool) -> None:
        """Set user active.

        Args:
            user_id (str): Value for ``user_id``.
            is_active (bool): Value for ``is_active``.

        Returns:
            None.
        """
        self.user_handler.toggle_user_active(user_id, is_active)

    def list_roles(self) -> list[dict[str, Any]]:
        """List roles.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return [dict(item) for item in (self.roles_handler.get_all_roles() or []) if isinstance(item, dict)]

    def get_role(self, role_id: str) -> dict[str, Any] | None:
        """Return role.

        Args:
            role_id (str): Value for ``role_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return self.roles_handler.get_role(role_id)

    def create_role(self, role_data: dict[str, Any]) -> None:
        """Create role.

        Args:
            role_data (dict[str, Any]): Value for ``role_data``.

        Returns:
            None.
        """
        self.roles_handler.create_role(role_data)

    def update_role(self, role_id: str, role_data: dict[str, Any]) -> None:
        """Update role.

        Args:
            role_id (str): Value for ``role_id``.
            role_data (dict[str, Any]): Value for ``role_data``.

        Returns:
            None.
        """
        self.roles_handler.update_role(role_id, role_data)

    def delete_role(self, role_id: str) -> None:
        """Delete role.

        Args:
            role_id (str): Value for ``role_id``.

        Returns:
            None.
        """
        self.roles_handler.delete_role(role_id)

    def set_role_active(self, role_id: str, is_active: bool) -> None:
        """Set role active.

        Args:
            role_id (str): Value for ``role_id``.
            is_active (bool): Value for ``is_active``.

        Returns:
            None.
        """
        self.roles_handler.toggle_role_active(role_id, is_active)

    def get_role_colors(self) -> dict[str, Any]:
        """Return role colors.

        Returns:
            dict[str, Any]: The function result.
        """
        return self.roles_handler.get_role_colors()

    def get_role_names(self) -> list[str]:
        """Return role names.

        Returns:
            list[str]: The function result.
        """
        return list(self.roles_handler.get_all_role_names() or [])

    def get_roles_policy_map(self) -> dict[str, dict[str, Any]]:
        """Return roles policy map.

        Returns:
            dict[str, dict[str, Any]]: The function result.
        """
        return {
            role["role_id"]: {
                "permissions": role.get("permissions", []),
                "deny_permissions": role.get("deny_permissions", []),
                "level": role.get("level", 0),
            }
            for role in self.list_roles()
            if role.get("role_id")
        }

    def list_permission_policy_options(self) -> list[dict[str, Any]]:
        """List permission policy options.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        permission_policies = self.permissions_handler.get_all_permissions(is_active=True)
        return [
            {
                "value": permission.get("permission_id"),
                "label": permission.get("label", permission.get("permission_id")),
                "category": permission.get("category", "Uncategorized"),
            }
            for permission in permission_policies
        ]

    def list_permissions(self, *, is_active: bool = False) -> list[dict[str, Any]]:
        """List permissions.

        Args:
            is_active (bool): Value for ``is_active``.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return [
            dict(item)
            for item in (self.permissions_handler.get_all_permissions(is_active=is_active) or [])
            if isinstance(item, dict)
        ]

    def get_permission(self, permission_id: str) -> dict[str, Any] | None:
        """Return permission.

        Args:
            permission_id (str): Value for ``permission_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return self.permissions_handler.get_permission(permission_id)

    def create_permission(self, policy: dict[str, Any]) -> None:
        """Create permission.

        Args:
            policy (dict[str, Any]): Value for ``policy``.

        Returns:
            None.
        """
        self.permissions_handler.create_new_policy(policy)

    def update_permission(self, permission_id: str, policy: dict[str, Any]) -> None:
        """Update permission.

        Args:
            permission_id (str): Value for ``permission_id``.
            policy (dict[str, Any]): Value for ``policy``.

        Returns:
            None.
        """
        self.permissions_handler.update_policy(permission_id, policy)

    def set_permission_active(self, permission_id: str, is_active: bool) -> None:
        """Set permission active.

        Args:
            permission_id (str): Value for ``permission_id``.
            is_active (bool): Value for ``is_active``.

        Returns:
            None.
        """
        self.permissions_handler.toggle_policy_active(permission_id, is_active)

    def delete_permission(self, permission_id: str) -> None:
        """Delete permission.

        Args:
            permission_id (str): Value for ``permission_id``.

        Returns:
            None.
        """
        self.permissions_handler.delete_policy(permission_id)

    def get_assay_group_map(self) -> dict[str, list[dict[str, Any]]]:
        """Return assay group map.

        Returns:
            dict[str, list[dict[str, Any]]]: The function result.
        """
        assay_groups_panels = self.asp_handler.get_all_asps()
        return util.common.create_assay_group_map(assay_groups_panels)

    def get_asp_groups(self) -> list[str]:
        """Return asp groups.

        Returns:
            list[str]: The function result.
        """
        return list(self.asp_handler.get_all_asp_groups() or [])

    def list_panels(self, *, is_active: bool | None = None) -> list[dict[str, Any]]:
        """List panels.

        Args:
            is_active (bool | None): Value for ``is_active``.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return [dict(item) for item in (self.asp_handler.get_all_asps(is_active=is_active) or []) if isinstance(item, dict)]

    def get_panel(self, panel_id: str) -> dict[str, Any] | None:
        """Return panel.

        Args:
            panel_id (str): Value for ``panel_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return self.asp_handler.get_asp(panel_id)

    def create_panel(self, panel: dict[str, Any]) -> None:
        """Create panel.

        Args:
            panel (dict[str, Any]): Value for ``panel``.

        Returns:
            None.
        """
        self.asp_handler.create_asp(panel)

    def update_panel(self, panel_id: str, panel: dict[str, Any]) -> None:
        """Update panel.

        Args:
            panel_id (str): Value for ``panel_id``.
            panel (dict[str, Any]): Value for ``panel``.

        Returns:
            None.
        """
        self.asp_handler.update_asp(panel_id, panel)

    def set_panel_active(self, panel_id: str, is_active: bool) -> None:
        """Set panel active.

        Args:
            panel_id (str): Value for ``panel_id``.
            is_active (bool): Value for ``is_active``.

        Returns:
            None.
        """
        self.asp_handler.toggle_asp_active(panel_id, is_active)

    def delete_panel(self, panel_id: str) -> None:
        """Delete panel.

        Args:
            panel_id (str): Value for ``panel_id``.

        Returns:
            None.
        """
        self.asp_handler.delete_asp(panel_id)

    def list_genelists(self) -> list[dict[str, Any]]:
        """List genelists.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return [dict(item) for item in (self.isgl_handler.get_all_isgl() or []) if isinstance(item, dict)]

    def get_genelist(self, genelist_id: str) -> dict[str, Any] | None:
        """Return genelist.

        Args:
            genelist_id (str): Value for ``genelist_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return self.isgl_handler.get_isgl(genelist_id)

    def create_genelist(self, genelist: dict[str, Any]) -> None:
        """Create genelist.

        Args:
            genelist (dict[str, Any]): Value for ``genelist``.

        Returns:
            None.
        """
        self.isgl_handler.create_isgl(genelist)

    def update_genelist(self, genelist_id: str, genelist: dict[str, Any]) -> None:
        """Update genelist.

        Args:
            genelist_id (str): Value for ``genelist_id``.
            genelist (dict[str, Any]): Value for ``genelist``.

        Returns:
            None.
        """
        self.isgl_handler.update_isgl(genelist_id, genelist)

    def set_genelist_active(self, genelist_id: str, is_active: bool) -> None:
        """Set genelist active.

        Args:
            genelist_id (str): Value for ``genelist_id``.
            is_active (bool): Value for ``is_active``.

        Returns:
            None.
        """
        self.isgl_handler.toggle_isgl_active(genelist_id, is_active)

    def delete_genelist(self, genelist_id: str) -> None:
        """Delete genelist.

        Args:
            genelist_id (str): Value for ``genelist_id``.

        Returns:
            None.
        """
        self.isgl_handler.delete_isgl(genelist_id)

    def list_assay_configs(self) -> list[dict[str, Any]]:
        """List assay configs.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return [dict(item) for item in (self.aspc_handler.get_all_aspc() or []) if isinstance(item, dict)]

    def get_assay_config(self, assay_id: str) -> dict[str, Any] | None:
        """Return assay config.

        Args:
            assay_id (str): Value for ``assay_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return self.aspc_handler.get_aspc_with_id(assay_id)

    def create_assay_config(self, config: dict[str, Any]) -> None:
        """Create assay config.

        Args:
            config (dict[str, Any]): Value for ``config``.

        Returns:
            None.
        """
        self.aspc_handler.create_aspc(config)

    def update_assay_config(self, assay_id: str, config: dict[str, Any]) -> None:
        """Update assay config.

        Args:
            assay_id (str): Value for ``assay_id``.
            config (dict[str, Any]): Value for ``config``.

        Returns:
            None.
        """
        self.aspc_handler.update_aspc(assay_id, config)

    def set_assay_config_active(self, assay_id: str, is_active: bool) -> None:
        """Set assay config active.

        Args:
            assay_id (str): Value for ``assay_id``.
            is_active (bool): Value for ``is_active``.

        Returns:
            None.
        """
        self.aspc_handler.toggle_aspc_active(assay_id, is_active)

    def delete_assay_config(self, assay_id: str) -> None:
        """Delete assay config.

        Args:
            assay_id (str): Value for ``assay_id``.

        Returns:
            None.
        """
        self.aspc_handler.delete_aspc(assay_id)

    def get_available_assay_envs(self, assay_id: str, allowed_envs: list[str]) -> list[str]:
        """Return available assay envs.

        Args:
            assay_id (str): Value for ``assay_id``.
            allowed_envs (list[str]): Value for ``allowed_envs``.

        Returns:
            list[str]: The function result.
        """
        return list(self.aspc_handler.get_available_assay_envs(assay_id, allowed_envs) or [])

    def list_samples_for_admin(self, *, assays: list[str], search: str) -> list[dict[str, Any]]:
        """List samples for admin.

        Args:
            assays (list[str]): Value for ``assays``.
            search (str): Value for ``search``.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return [dict(item) for item in (self.sample_handler.get_all_samples(assays, None, search) or []) if isinstance(item, dict)]

    def get_sample(self, sample_id: str) -> dict[str, Any] | None:
        """Return sample.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        return self.sample_handler.get_sample(sample_id)

    def update_sample(self, sample_obj: Any, updated_sample: dict[str, Any]) -> None:
        """Update sample.

        Args:
            sample_obj (Any): Value for ``sample_obj``.
            updated_sample (dict[str, Any]): Value for ``updated_sample``.

        Returns:
            None.
        """
        self.sample_handler.update_sample(sample_obj, updated_sample)

    def get_sample_name(self, sample_id: str) -> str | None:
        """Return sample name.

        Args:
            sample_id (str): Value for ``sample_id``.

        Returns:
            str | None: The function result.
        """
        return self.sample_handler.get_sample_name(sample_id)

    def list_schemas(self) -> list[dict[str, Any]]:
        """List schemas.

        Returns:
            list[dict[str, Any]]: The function result.
        """
        return [dict(item) for item in (self.schema_handler.get_all_schemas() or []) if isinstance(item, dict)]

    def create_schema(self, schema_doc: dict[str, Any]) -> None:
        """Create schema.

        Args:
            schema_doc (dict[str, Any]): Value for ``schema_doc``.

        Returns:
            None.
        """
        self.schema_handler.create_schema(schema_doc)

    def update_schema(self, schema_id: str, schema_doc: dict[str, Any]) -> None:
        """Update schema.

        Args:
            schema_id (str): Value for ``schema_id``.
            schema_doc (dict[str, Any]): Value for ``schema_doc``.

        Returns:
            None.
        """
        self.schema_handler.update_schema(schema_id, schema_doc)

    def set_schema_active(self, schema_id: str, is_active: bool) -> None:
        """Set schema active.

        Args:
            schema_id (str): Value for ``schema_id``.
            is_active (bool): Value for ``is_active``.

        Returns:
            None.
        """
        self.schema_handler.toggle_schema_active(schema_id, is_active)

    def delete_schema(self, schema_id: str) -> None:
        """Delete schema.

        Args:
            schema_id (str): Value for ``schema_id``.

        Returns:
            None.
        """
        self.schema_handler.delete_schema(schema_id)

    def get_active_schema(self, *, schema_type: str, schema_category: str, schema_id: str | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Return active schema.

        Args:
            schema_type (str): Value for ``schema_type``.
            schema_category (str): Value for ``schema_category``.
            schema_id (str | None): Value for ``schema_id``.

        Returns:
            tuple[list[dict[str, Any]], dict[str, Any]]: The function result.
        """
        active_schemas = self.schema_handler.get_schemas_by_category_type(
            schema_type=schema_type,
            schema_category=schema_category,
            is_active=True,
        )
        if not active_schemas:
            return [], {}
        selected_id = schema_id or active_schemas[0].get("_id")
        selected_schema = next((schema for schema in active_schemas if schema.get("_id") == selected_id), {})
        return active_schemas, selected_schema

    def get_schema(self, schema_name: str | None) -> dict[str, Any] | None:
        """Return schema.

        Args:
            schema_name (str | None): Value for ``schema_name``.

        Returns:
            dict[str, Any] | None: The function result.
        """
        if not schema_name:
            return None
        schema = self.schema_handler.get_schema(schema_name)
        return dict(schema) if isinstance(schema, dict) else schema

    def clone_schema(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Handle clone schema.

        Args:
            schema (dict[str, Any]): Value for ``schema``.

        Returns:
            dict[str, Any]: The function result.
        """
        return deepcopy(schema)


__all__ = ["AdminRepository", "AdminSampleDeletionRepository"]
