"""Unit tests for admin workflow services."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

import api.application.accounts.permissions as admin_permission_service_module
import api.application.accounts.roles as admin_role_service_module
import api.application.accounts.users as admin_user_service_module
import api.application.resources.asp as admin_asp_service_module
import api.application.resources.aspc as admin_aspc_service_module
import api.application.resources.isgl as admin_isgl_service_module
import api.application.resources.sample as admin_resource_service_module
from api.app.container import util as shared_util
from api.application.accounts.permissions import PermissionManagementService
from api.application.accounts.roles import RoleManagementService
from api.application.accounts.users import UserManagementService
from api.application.resources.asp import AspService
from api.application.resources.aspc import AspcService
from api.application.resources.isgl import IsglService
from api.application.resources.sample import ResourceSampleService
from api.config.constants import (
    ASP_CATEGORY_OPTIONS,
    ASP_FAMILY_OPTIONS,
    ASP_GROUP_OPTIONS,
    PLATFORM_OPTIONS,
    SAMPLE_FILE_KEYS,
)
from api.config.contracts.governance import PERMISSION_CATALOG
from api.contracts.operations import OperationResult
from api.domain.core.exceptions import AppError


class _AdminRepoStub:
    """Provide  AdminRepoStub behavior."""

    def __init__(self) -> None:
        """__init__."""
        self.created_user = None
        self.updated_user = None
        self.created_role = None
        self.updated_role = None
        self.deleted_users: list[str] = []
        self.deleted_roles: list[str] = []

    def list_users(self):
        """List users.

        Returns:
            The function result.
        """
        return [{"_id": "tester", "user_id": "tester"}]

    def search_users(self, *, q="", page=1, per_page=30):
        """Search users."""
        _ = (q, page, per_page)
        return ([{"_id": "tester", "user_id": "tester"}], 1)

    def get_role_colors(self):
        """Return role colors.

        Returns:
            The function result.
        """
        return {"admin": "#000"}

    def list_permission_policy_options(self):
        """List permission policy options.

        Returns:
            The function result.
        """
        return [{"value": "perm.a", "label": "perm.a", "category": "General"}]

    def get_role_names(self):
        """Return role names.

        Returns:
            The function result.
        """
        return ["admin"]

    def get_roles_policy_map(self):
        """Return roles policy map.

        Returns:
            The function result.
        """
        return {"admin": {"permissions": ["perm.a"], "level": 99}}

    def get_assay_group_map(self):
        """Return assay group map.

        Returns:
            The function result.
        """
        return {"dna": [{"_id": "WGS"}]}

    def get_asp_groups(self):
        """Return asp groups.

        Returns:
            The function result.
        """
        return ["dna"]

    def create_user(self, user_data):
        """Create user.

        Args:
            user_data: Value for ``user_data``.

        Returns:
            The function result.
        """
        self.created_user = user_data

    def get_user(self, user_id):
        """Return user.

        Args:
            user_id: Value for ``user_id``.

        Returns:
            The function result.
        """
        if user_id in {"missing", "newtester"}:
            return None
        return {
            "_id": "tester",
            "username": "tester",
            "email": "tester@example.com",
            "firstname": "Test",
            "lastname": "User",
            "fullname": "Test User",
            "job_title": "Analyst",
            "roles": ["admin"],
            "password": "hashed",
            "version": 3,
            "asp_groups": [],
            "asp_ids": [],
            "environments": ["production"],
            "is_active": True,
            "auth_type": ["ldap"],
        }

    def update_user(self, user_id, user_data):
        """Update user.

        Args:
            user_id: Value for ``user_id``.
            user_data: Value for ``user_data``.

        Returns:
            The function result.
        """
        self.updated_user = (user_id, user_data)

    def delete_user(self, user_id):
        """Delete user.

        Args:
            user_id: Value for ``user_id``.

        Returns:
            The function result.
        """
        self.deleted_users.append(user_id)

    def set_user_active(self, user_id, is_active):
        """Set user active.

        Args:
            user_id: Value for ``user_id``.
            is_active: Value for ``is_active``.

        Returns:
            The function result.
        """
        self.updated_user = (user_id, {"is_active": is_active})

    @property
    def user_repository(self):
        """User handler.

        Returns:
            The function result.
        """
        return type(
            "_UserHandler",
            (),
            {
                "user_exists": staticmethod(
                    lambda **kwargs: (
                        kwargs.get("user_id") == "taken"
                        or kwargs.get("email") == "taken@example.com"
                    )
                )
            },
        )()

    def list_roles(self):
        """List roles.

        Returns:
            The function result.
        """
        return [{"_id": "admin", "role_id": "admin", "level": 99}]

    def search_roles(self, *, q="", page=1, per_page=30):
        """Search roles."""
        _ = (q, page, per_page)
        return ([{"_id": "admin", "role_id": "admin", "level": 99}], 1)

    def get_role(self, role_id):
        """Return role.

        Args:
            role_id: Value for ``role_id``.

        Returns:
            The function result.
        """
        if role_id in {"missing", "developer"}:
            return None
        return {
            "_id": "admin",
            "role_id": "admin",
            "name": "Admin",
            "permissions": [],
            "version": 4,
        }

    def create_role(self, role_data):
        """Create role.

        Args:
            role_data: Value for ``role_data``.

        Returns:
            The function result.
        """
        self.created_role = role_data

    def update_role(self, role_id, role_data):
        """Update role.

        Args:
            role_id: Value for ``role_id``.
            role_data: Value for ``role_data``.

        Returns:
            The function result.
        """
        self.updated_role = (role_id, role_data)

    def set_role_active(self, role_id, is_active):
        """Set role active.

        Args:
            role_id: Value for ``role_id``.
            is_active: Value for ``is_active``.

        Returns:
            The function result.
        """
        self.updated_role = (role_id, {"is_active": is_active})

    def delete_role(self, role_id):
        """Delete role.

        Args:
            role_id: Value for ``role_id``.

        Returns:
            The function result.
        """
        self.deleted_roles.append(role_id)

    def list_permissions(self, *, is_active=False):
        """List permissions.

        Args:
            is_active: Value for ``is_active``.

        Returns:
            The function result.
        """
        return [
            {
                "_id": "sample:view",
                "permission_id": "sample:view",
                "category": "General",
                "is_active": True,
            }
        ]

    def search_permissions(self, *, q="", page=1, per_page=30, is_active=False):
        """Search permissions."""
        _ = (q, page, per_page, is_active)
        return (
            [
                {
                    "_id": "sample:view",
                    "permission_id": "sample:view",
                    "category": "General",
                    "is_active": True,
                }
            ],
            1,
        )

    def get_permission(self, permission_id):
        """Return permission.

        Args:
            permission_id: Value for ``permission_id``.

        Returns:
            The function result.
        """
        if permission_id in {"missing", "sample:create"}:
            return None
        return {
            "_id": permission_id,
            "permission_id": permission_id,
            "version": 4,
            "is_active": True,
            "category": "General",
        }

    def create_permission(self, policy):
        """Create permission.

        Args:
            policy: Value for ``policy``.

        Returns:
            The function result.
        """
        self.created_permission = policy

    def update_permission(self, permission_id, policy):
        """Update permission.

        Args:
            permission_id: Value for ``permission_id``.
            policy: Value for ``policy``.

        Returns:
            The function result.
        """
        self.updated_permission = (permission_id, policy)

    def set_permission_active(self, permission_id, is_active):
        """Set permission active.

        Args:
            permission_id: Value for ``permission_id``.
            is_active: Value for ``is_active``.

        Returns:
            The function result.
        """
        self.updated_permission = (permission_id, {"is_active": is_active})

    def delete_permission(self, permission_id):
        """Delete permission.

        Args:
            permission_id: Value for ``permission_id``.

        Returns:
            The function result.
        """
        self.deleted_permissions = getattr(self, "deleted_permissions", [])
        self.deleted_permissions.append(permission_id)

    def list_panels(self, *, is_active=None):
        """List panels.

        Args:
            is_active: Value for ``is_active``.

        Returns:
            The function result.
        """

    def get_panel(self, panel_id):
        """Return panel.

        Args:
            panel_id: Value for ``panel_id``.

        Returns:
            The function result.
        """
        if panel_id == "missing":
            return None
        return {
            "_id": panel_id,
            "asp_id": panel_id,
            "asp_group": "dna",
            "is_active": False,
            "covered_genes": ["TP53"],
            "germline_genes": ["BRCA1"],
        }

    def create_panel(self, panel):
        """Create panel.

        Args:
            panel: Value for ``panel``.

        Returns:
            The function result.
        """
        self.created_panel = panel

    def update_panel(self, panel_id, panel):
        """Update panel.

        Args:
            panel_id: Value for ``panel_id``.
            panel: Value for ``panel``.

        Returns:
            The function result.
        """
        self.updated_panel = (panel_id, panel)

    def rotate_panel(self, panel_id, panel, expected_version=None, retire_fields=None):
        """Rotate panel.

        Args:
            panel_id: Value for ``panel_id``.
            panel: Value for ``panel``.
            retire_fields: Value for ``retire_fields``.

        Returns:
            The function result.
        """
        self.updated_panel = (panel_id, panel, expected_version, retire_fields or {})
        return OperationResult(inserted_count=1, inserted_id="new-panel-id")

    def set_panel_active(self, panel_id, is_active):
        """Set panel active.

        Args:
            panel_id: Value for ``panel_id``.
            is_active: Value for ``is_active``.

        Returns:
            The function result.
        """
        self.updated_panel = (panel_id, {"is_active": is_active})

    def delete_panel(self, panel_id):
        """Delete panel.

        Args:
            panel_id: Value for ``panel_id``.

        Returns:
            The function result.
        """
        self.deleted_panels = getattr(self, "deleted_panels", [])
        self.deleted_panels.append(panel_id)

    def list_genelists(self):
        """List genelists.

        Returns:
            The function result.
        """
        return [
            {
                "_id": "GL1",
                "isgl_id": "GL1",
                "genes": ["TP53"],
                "asp_ids": ["WGS"],
            }
        ]

    def get_genelist(self, genelist_id):
        """Return genelist.

        Args:
            genelist_id: Value for ``genelist_id``.

        Returns:
            The function result.
        """
        if genelist_id == "missing":
            return None
        return {
            "_id": genelist_id,
            "isgl_id": genelist_id,
            "genes": ["TP53", "EGFR"],
            "asp_ids": ["WGS"],
            "asp_groups": ["dna"],
            "is_active": True,
        }

    def create_genelist(self, genelist):
        """Create genelist.

        Args:
            genelist: Value for ``genelist``.

        Returns:
            The function result.
        """
        self.created_genelist = genelist

    def update_genelist(self, genelist_id, genelist):
        """Update genelist.

        Args:
            genelist_id: Value for ``genelist_id``.
            genelist: Value for ``genelist``.

        Returns:
            The function result.
        """
        self.updated_genelist = (genelist_id, genelist)

    def rotate_genelist(self, genelist_id, genelist, expected_version=None, retire_fields=None):
        """Rotate genelist.

        Args:
            genelist_id: Value for ``genelist_id``.
            genelist: Value for ``genelist``.
            retire_fields: Value for ``retire_fields``.

        Returns:
            The function result.
        """
        self.updated_genelist = (genelist_id, genelist, expected_version, retire_fields or {})
        return OperationResult(inserted_count=1, inserted_id="new-genelist-id")

    def set_genelist_active(self, genelist_id, is_active):
        """Set genelist active.

        Args:
            genelist_id: Value for ``genelist_id``.
            is_active: Value for ``is_active``.

        Returns:
            The function result.
        """
        self.updated_genelist = (genelist_id, {"is_active": is_active})

    def delete_genelist(self, genelist_id):
        """Delete genelist.

        Args:
            genelist_id: Value for ``genelist_id``.

        Returns:
            The function result.
        """
        self.deleted_genelists = getattr(self, "deleted_genelists", [])
        self.deleted_genelists.append(genelist_id)

    def list_assay_configs(self):
        """List assay configs.

        Returns:
            The function result.
        """
        return [{"_id": "WGS:prod", "aspc_id": "WGS:prod", "is_active": True}]

    def get_assay_config(self, assay_id):
        """Return assay config.

        Args:
            assay_id: Value for ``assay_id``.

        Returns:
            The function result.
        """
        if assay_id == "missing":
            return None
        return {"_id": assay_id, "aspc_id": assay_id, "is_active": True}

    def create_assay_config(self, config):
        """Create assay config.

        Args:
            config: Value for ``config``.

        Returns:
            The function result.
        """
        self.created_aspc = config

    def update_assay_config(self, assay_id, config):
        """Update assay config.

        Args:
            assay_id: Value for ``assay_id``.
            config: Value for ``config``.

        Returns:
            The function result.
        """
        self.updated_aspc = (assay_id, config)

    def rotate_assay_config(self, assay_id, config, expected_version=None, retire_fields=None):
        """Rotate assay config.

        Args:
            assay_id: Value for ``assay_id``.
            config: Value for ``config``.
            retire_fields: Value for ``retire_fields``.

        Returns:
            The function result.
        """
        self.updated_aspc = (assay_id, config, expected_version, retire_fields or {})
        return OperationResult(inserted_count=1, inserted_id="new-aspc-id")

    def set_assay_config_active(self, assay_id, is_active):
        """Set assay config active.

        Args:
            assay_id: Value for ``assay_id``.
            is_active: Value for ``is_active``.

        Returns:
            The function result.
        """
        self.updated_aspc = (assay_id, {"is_active": is_active})

    def delete_assay_config(self, assay_id):
        """Delete assay config.

        Args:
            assay_id: Value for ``assay_id``.

        Returns:
            The function result.
        """
        self.deleted_aspc = getattr(self, "deleted_aspc", [])
        self.deleted_aspc.append(assay_id)

    def get_available_assay_envs(self, assay_id, allowed_envs):
        """Return available assay envs.

        Args:
            assay_id: Value for ``assay_id``.
            allowed_envs: Value for ``allowed_envs``.

        Returns:
            The function result.
        """
        return ["production"]

    def list_samples_for_admin(
        self,
        *,
        asp_ids=None,
        search_str="",
        page=1,
        per_page=30,
        ready_only=True,
    ):
        """List samples for admin.

        Args:
            asp_ids: Value for ``asp_ids``.
            search_str: Value for ``search_str``.

        Returns:
            The function result.
        """
        _ = (asp_ids, search_str, page, per_page, ready_only)
        return ([{"_id": "S1"}], 1)

    def search_panels(self, *, q="", page=1, per_page=30, is_active=None):
        """Search panels."""
        _ = (q, page, per_page, is_active)
        return ([{"_id": "asp1"}], 1)

    def search_genelists(self, *, q="", page=1, per_page=30):
        """Search genelists."""
        _ = (q, page, per_page)
        return ([{"_id": "isgl1"}], 1)

    def search_assay_configs(self, *, q="", page=1, per_page=30):
        """Search assay configs."""
        _ = (q, page, per_page)
        return ([{"_id": "aspc1"}], 1)

    def search_schemas(self, *, q="", page=1, per_page=30):
        """Search schemas."""
        _ = (q, page, per_page)
        return ([{"_id": "schema1"}], 1)

    def get_sample(self, sample_id):
        """Return sample.

        Args:
            sample_id: Value for ``sample_id``.

        Returns:
            The function result.
        """
        if sample_id == "missing":
            return None
        return {"_id": sample_id, "sample_id": sample_id}

    def update_sample(self, sample_obj, updated_sample):
        """Update sample.

        Args:
            sample_obj: Value for ``sample_obj``.
            updated_sample: Value for ``updated_sample``.

        Returns:
            The function result.
        """
        self.updated_sample_doc = (sample_obj, updated_sample)

    def get_sample_name(self, sample_id):
        """Return sample name.

        Args:
            sample_id: Value for ``sample_id``.

        Returns:
            The function result.
        """
        if sample_id == "missing":
            return None
        return sample_id

    def list_schemas(self):
        """List schemas.

        Returns:
            The function result.
        """
        return [{"_id": "schema1"}]

    def create_schema(self, schema_doc):
        """Create schema.

        Args:
            schema_doc: Value for ``schema_doc``.

        Returns:
            The function result.
        """
        self.created_schema = schema_doc

    def update_schema(self, schema_id, schema_doc):
        """Update schema.

        Args:
            schema_id: Value for ``schema_id``.
            schema_doc: Value for ``schema_doc``.

        Returns:
            The function result.
        """
        self.updated_schema = (schema_id, schema_doc)

    def set_schema_active(self, schema_id, is_active):
        """Set schema active.

        Args:
            schema_id: Value for ``schema_id``.
            is_active: Value for ``is_active``.

        Returns:
            The function result.
        """
        self.updated_schema = (schema_id, {"is_active": is_active})

    def delete_schema(self, schema_id):
        """Delete schema.

        Args:
            schema_id: Value for ``schema_id``.

        Returns:
            The function result.
        """
        self.deleted_schemas = getattr(self, "deleted_schemas", [])
        self.deleted_schemas.append(schema_id)


def _build_store(repo: _AdminRepoStub) -> SimpleNamespace:
    return SimpleNamespace(
        user_repository=SimpleNamespace(
            search_users=repo.search_users,
            user_with_id=repo.get_user,
            create_user=repo.create_user,
            update_user=repo.update_user,
            toggle_user_active=repo.set_user_active,
            delete_user=repo.delete_user,
            user_exists=repo.user_repository.user_exists,
        ),
        roles_repository=SimpleNamespace(
            search_roles=repo.search_roles,
            get_role_colors=repo.get_role_colors,
            get_all_role_names=repo.get_role_names,
            get_all_roles=lambda: [
                {
                    "role_id": role_id,
                    "permissions": role_data.get("permissions", []),
                    "level": role_data.get("level", 0),
                }
                for role_id, role_data in repo.get_roles_policy_map().items()
            ],
            get_role=repo.get_role,
            create_role=repo.create_role,
            update_role=repo.update_role,
            toggle_role_active=repo.set_role_active,
            delete_role=repo.delete_role,
        ),
        permissions_repository=SimpleNamespace(
            search_permissions=repo.search_permissions,
            get_all_permissions=repo.list_permissions,
            get_permission=repo.get_permission,
            create_new_policy=repo.create_permission,
            update_policy=repo.update_permission,
            toggle_policy_active=repo.set_permission_active,
            delete_policy=repo.delete_permission,
        ),
        vep_metadata_repository=SimpleNamespace(
            get_consequence_group_options=lambda vep=None: ["missense", "splicing"],
        ),
        assay_panel_repository=SimpleNamespace(
            search_asps=repo.search_panels,
            get_all_asp_groups=repo.get_asp_groups,
            get_all_asps=lambda is_active=None: [repo.get_panel("WGS")],
            get_asp=repo.get_panel,
            create_panel=repo.create_panel,
            update_asp=repo.update_panel,
            rotate_asp=repo.rotate_panel,
            toggle_asp_active=repo.set_panel_active,
            delete_panel=repo.delete_panel,
        ),
        gene_list_repository=SimpleNamespace(
            search_isgls=repo.search_genelists,
            get_all_isgl=repo.list_genelists,
            get_isgl=repo.get_genelist,
            get_isgl_for_scope=lambda asp_name=None, assay_group=None, is_active=None, adhoc=None: [
                item
                for item in repo.list_genelists()
                if (
                    asp_name in (item.get("asp_ids") or [])
                    or assay_group in (item.get("asp_groups") or [])
                )
                and (is_active is None or item.get("is_active") is is_active)
                and (adhoc is None or item.get("adhoc") is adhoc)
            ],
            create_genelist=repo.create_genelist,
            update_isgl=repo.update_genelist,
            rotate_isgl=repo.rotate_genelist,
            toggle_isgl_active=repo.set_genelist_active,
            delete_genelist=repo.delete_genelist,
        ),
        assay_configuration_repository=SimpleNamespace(
            search_aspcs=repo.search_assay_configs,
            get_aspc=repo.get_assay_config,
            get_aspc_with_id=repo.get_assay_config,
            get_available_assay_envs=repo.get_available_assay_envs,
            create_assay_config=repo.create_assay_config,
            update_aspc=repo.update_assay_config,
            rotate_aspc=repo.rotate_assay_config,
            toggle_aspc_active=repo.set_assay_config_active,
            delete_assay_config=repo.delete_assay_config,
        ),
        sample_repository=SimpleNamespace(
            search_samples_for_admin=repo.list_samples_for_admin,
            get_sample=repo.get_sample,
            update_sample=repo.update_sample,
            get_sample_name=repo.get_sample_name,
        ),
        variant_repository=SimpleNamespace(),
        copy_number_variant_repository=SimpleNamespace(),
        coverage_repository=SimpleNamespace(),
        translocation_repository=SimpleNamespace(),
        fusion_repository=SimpleNamespace(),
        biomarker_repository=SimpleNamespace(),
        rna_expression_repository=SimpleNamespace(),
        rna_classification_repository=SimpleNamespace(),
        rna_quality_repository=SimpleNamespace(),
        pgx_repository=SimpleNamespace(),
        sample_comment_repository=SimpleNamespace(),
        finding_comment_repository=SimpleNamespace(),
        report_repository=SimpleNamespace(),
        reported_variant_repository=SimpleNamespace(),
        oncokb_public_cache_repository=SimpleNamespace(),
    )


def _user_service(repo: _AdminRepoStub) -> UserManagementService:
    store = _build_store(repo)
    return UserManagementService(
        user_repository=store.user_repository,
        roles_repository=store.roles_repository,
        permissions_repository=store.permissions_repository,
        assay_panel_repository=store.assay_panel_repository,
        common_util=shared_util.common,
    )


def _role_service(repo: _AdminRepoStub) -> RoleManagementService:
    store = _build_store(repo)
    return RoleManagementService(
        roles_repository=store.roles_repository,
        permissions_repository=store.permissions_repository,
    )


def _permission_service(repo: _AdminRepoStub) -> PermissionManagementService:
    store = _build_store(repo)
    return PermissionManagementService(permissions_repository=store.permissions_repository)


def _asp_service(repo: _AdminRepoStub) -> AspService:
    store = _build_store(repo)
    return AspService(assay_panel_repository=store.assay_panel_repository)


def _isgl_service(repo: _AdminRepoStub) -> IsglService:
    store = _build_store(repo)
    return IsglService(
        gene_list_repository=store.gene_list_repository,
        assay_panel_repository=store.assay_panel_repository,
    )


def _aspc_service(repo: _AdminRepoStub) -> AspcService:
    store = _build_store(repo)
    return AspcService(
        assay_configuration_repository=store.assay_configuration_repository,
        assay_panel_repository=store.assay_panel_repository,
        gene_list_repository=store.gene_list_repository,
        vep_metadata_repository=store.vep_metadata_repository,
        common_util=shared_util.common,
    )


def _resource_sample_service(repo: _AdminRepoStub) -> ResourceSampleService:
    store = _build_store(repo)
    return ResourceSampleService(
        sample_repository=store.sample_repository,
        variant_repository=store.variant_repository,
        copy_number_variant_repository=store.copy_number_variant_repository,
        coverage_repository=store.coverage_repository,
        translocation_repository=store.translocation_repository,
        fusion_repository=store.fusion_repository,
        biomarker_repository=store.biomarker_repository,
        rna_expression_repository=store.rna_expression_repository,
        rna_classification_repository=store.rna_classification_repository,
        rna_quality_repository=store.rna_quality_repository,
        pgx_repository=store.pgx_repository,
        sample_comment_repository=store.sample_comment_repository,
        finding_comment_repository=store.finding_comment_repository,
        report_repository=store.report_repository,
        reported_variant_repository=store.reported_variant_repository,
        assay_panel_repository=store.assay_panel_repository,
    )


def _patch_admin_stores(monkeypatch, repo: _AdminRepoStub) -> None:
    store = _build_store(repo)
    for module in (
        admin_user_service_module,
        admin_role_service_module,
        admin_permission_service_module,
        admin_asp_service_module,
        admin_aspc_service_module,
        admin_isgl_service_module,
        admin_resource_service_module,
    ):
        monkeypatch.setattr(module, "store", store, raising=False)


def test_admin_user_service_create_user_normalizes_identity(monkeypatch):
    """Test admin user service create user normalizes identity.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _user_service(repo)
    monkeypatch.setattr("api.application.accounts.users.current_actor", lambda username: username)
    monkeypatch.setattr(
        "api.application.accounts.users.utc_now", lambda: datetime.now(timezone.utc)
    )
    monkeypatch.setattr(
        shared_util,
        "records",
        SimpleNamespace(
            normalize_form_payload=lambda form_data, schema: {
                "username": form_data["username"],
                "email": form_data["email"],
                "firstname": form_data.get("firstname", "Test"),
                "lastname": form_data.get("lastname", "User"),
                "fullname": form_data.get("fullname", "Test User"),
                "job_title": form_data.get("job_title", "Analyst"),
                "roles": form_data["roles"],
                "auth_type": ["ldap"],
                "password": "secret",
            }
        ),
        raising=False,
    )
    monkeypatch.setattr(
        shared_util,
        "common",
        SimpleNamespace(hash_password=lambda raw: f"H:{raw}"),
        raising=False,
    )
    service = UserManagementService(
        user_repository=service.user_repository,
        roles_repository=service.roles_repository,
        permissions_repository=service.permissions_repository,
        assay_panel_repository=service.assay_panel_repository,
        common_util=shared_util.common,
    )

    payload = service.create_user(
        payload={
            "form_data": {
                "username": "NewTester",
                "email": "NewTester@Example.com",
                "password": "secret",
                "roles": ["admin"],
            }
        },
        actor_username="actor@example.com",
    )

    assert payload["resource"] == "user"
    assert repo.created_user["username"] == "newtester"
    assert repo.created_user["email"] == "newtester@example.com"
    assert repo.created_user["auth_type"] == ["ldap"]
    assert repo.created_user["password"] is None
    assert "permissions" not in repo.created_user


def test_admin_user_service_toggle_user_sets_status(monkeypatch):
    """Test admin user service toggle user sets status.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _user_service(repo)

    payload = service.toggle_user(user_id="tester")

    assert payload["meta"]["is_active"] is False
    assert repo.updated_user == ("tester", {"is_active": False})


def test_admin_user_edit_rejects_password_fields():
    """Generic user administration must not mutate credentials."""
    service = _user_service(_AdminRepoStub())

    with pytest.raises(AppError, match="Passwords cannot be changed") as exc_info:
        service.update_user(
            user_id="tester",
            payload={"form_data": {"password": "replacement"}},
            actor_username="manager",
        )

    assert exc_info.value.status_code == 400


def test_non_superuser_cannot_assign_superuser_role():
    """The user-edit capability does not grant the superuser boundary."""
    service = _user_service(_AdminRepoStub())

    with pytest.raises(AppError, match="Only a superuser") as exc_info:
        service.create_user(
            payload={
                "form_data": {
                    "username": "elevated.user",
                    "email": "elevated@example.com",
                    "roles": ["superuser"],
                }
            },
            actor_username="manager",
        )

    assert exc_info.value.status_code == 403


def test_non_superuser_cannot_delete_or_disable_superuser(monkeypatch):
    """Delete and status changes preserve the privileged account boundary."""
    repo = _AdminRepoStub()
    monkeypatch.setattr(
        repo,
        "get_user",
        lambda _user_id: {
            "username": "root.user",
            "roles": ["superuser"],
            "is_active": True,
        },
    )
    service = _user_service(repo)

    with pytest.raises(AppError, match="Only a superuser"):
        service.delete_user(user_id="root.user")
    with pytest.raises(AppError, match="Only a superuser"):
        service.toggle_user(user_id="root.user")

    assert repo.deleted_users == []
    assert repo.updated_user is None


def test_user_can_update_only_safe_own_profile_fields():
    """Self-service profile editing cannot alter authorization or login identity."""
    repo = _AdminRepoStub()
    service = _user_service(repo)

    payload = service.update_own_profile(
        username="tester",
        payload={
            "firstname": "Updated",
            "lastname": "Name",
            "fullname": "Updated Name",
            "job_title": "Clinical Scientist",
        },
    )

    assert payload["user"]["fullname"] == "Updated Name"
    assert repo.updated_user[1]["email"] == "tester@example.com"
    assert repo.updated_user[1]["roles"] == ["admin"]
    assert repo.updated_user[1]["password"] == "hashed"

    with pytest.raises(AppError, match="cannot be edited"):
        service.update_own_profile(
            username="tester",
            payload={"roles": ["superuser"]},
        )


def test_user_can_update_only_validated_ui_settings():
    """Self-service UI settings persist independently of identity and authorization."""
    repo = _AdminRepoStub()
    service = _user_service(repo)

    payload = service.update_own_ui_settings(
        username="tester",
        payload={"analysis_layout": "modern", "analysis_modern_view_tried": True},
    )

    assert payload["ui_settings"] == {
        "analysis_layout": "modern",
        "sample_list_layout": "classic",
        "analysis_modern_view_tried": True,
        "sample_list_modern_view_tried": False,
        "table_page_size": 50,
    }
    assert repo.updated_user[1]["roles"] == ["admin"]
    assert repo.updated_user[1]["ui_settings"] == payload["ui_settings"]

    with pytest.raises(AppError, match="not supported"):
        service.update_own_ui_settings(
            username="tester",
            payload={"theme": "dark"},
        )


def test_admin_role_service_create_role_normalizes_business_key(monkeypatch):
    """Test admin role service create role normalizes business key.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _role_service(repo)
    monkeypatch.setattr("api.application.accounts.roles.current_actor", lambda username: username)
    monkeypatch.setattr(
        admin_role_service_module,
        "normalize_managed_form_payload",
        lambda _spec, form_data: {
            "name": form_data["name"],
            "label": form_data.get("name", ""),
            "color": "#1f2937",
            "level": 9999,
            "permissions": [],
        },
    )

    payload = service.create_role(
        payload={"form_data": {"name": "Developer"}}, actor_username="actor@example.com"
    )

    assert payload["resource"] == "role"
    assert repo.created_role["role_id"] == "developer"
    assert repo.created_role["name"] == "developer"
    assert repo.created_role["level"] == 9999
    assert "version_history" not in repo.created_role


def test_admin_role_service_delete_role_removes_existing_role(monkeypatch):
    """Test admin role service delete role removes existing role.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _role_service(repo)

    payload = service.delete_role(role_id="admin")

    assert payload["action"] == "delete"
    assert repo.deleted_roles == ["admin"]


def test_system_installed_role_cannot_be_deleted(monkeypatch):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    monkeypatch.setattr(
        repo,
        "get_role",
        lambda role_id: {"role_id": role_id, "system_managed": True},
    )

    with pytest.raises(AppError, match="System-installed role cannot be deleted"):
        _role_service(repo).delete_role(role_id="admin")

    assert repo.deleted_roles == []


def test_system_installed_user_cannot_be_deleted(monkeypatch):
    repo = _AdminRepoStub()
    monkeypatch.setattr(
        repo,
        "get_user",
        lambda user_id: {"username": user_id, "roles": ["superuser"], "system_managed": True},
    )

    with pytest.raises(AppError, match="System-installed user cannot be deleted"):
        _user_service(repo).delete_user(user_id="coyote3.admin", actor_is_superuser=True)

    assert repo.deleted_users == []


@pytest.mark.parametrize(
    ("service_factory", "repository_method", "delete_call", "message"),
    [
        (
            _asp_service,
            "get_panel",
            lambda service: service.delete(panel_id="demo_panel"),
            "System-installed assay panel cannot be deleted",
        ),
        (
            _aspc_service,
            "get_assay_config",
            lambda service: service.delete(assay_id="demo_panel_base_production"),
            "System-installed assay configuration cannot be deleted",
        ),
        (
            _isgl_service,
            "get_genelist",
            lambda service: service.delete(genelist_id="demo_genes"),
            "System-installed gene list cannot be deleted",
        ),
    ],
)
def test_system_installed_clinical_configuration_cannot_be_deleted(
    monkeypatch,
    service_factory,
    repository_method,
    delete_call,
    message,
):
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    monkeypatch.setattr(
        repo,
        repository_method,
        lambda resource_id: {"_id": resource_id, "system_managed": True},
    )

    with pytest.raises(AppError, match=message):
        delete_call(service_factory(repo))


def test_admin_permission_service_groups_permissions(monkeypatch):
    """Test admin permission service groups permissions.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _permission_service(repo)

    payload = service.list_permissions_payload()

    assert payload["permission_policies"][0]["permission_id"] == "sample:view"
    assert "General" in payload["grouped_permissions"]


def test_admin_permission_service_create_context_uses_backend_contract_form(monkeypatch):
    """Permission create-context should be served from the backend contract form."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _permission_service(repo)

    payload = service.create_context_payload(actor_username="actor@example.com")

    assert payload["form"]["form_type"] == "permission"
    assert payload["form"]["fields"]["created_by"]["default"] == "actor@example.com"
    assert payload["form"]["fields"]["category"]["options"] == list(PERMISSION_CATALOG.categories)


def test_admin_permission_service_toggle_permission_sets_status(monkeypatch):
    """Test admin permission service toggle permission sets status.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _permission_service(repo)

    payload = service.toggle_permission(permission_id="sample:view")

    assert payload["meta"]["is_active"] is False
    assert repo.updated_permission == ("sample:view", {"is_active": False})


def test_admin_panel_service_toggle_panel_sets_status(monkeypatch):
    """Test admin panel service toggle panel sets status.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _asp_service(repo)

    payload = service.toggle(panel_id="WGS")

    assert payload["meta"]["is_active"] is True
    assert repo.updated_panel == ("WGS", {"is_active": True})


def test_admin_panel_service_create_context_populates_asp_group_dropdown(monkeypatch):
    """ASP create-context should expose the fixed assay-group vocabulary."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _asp_service(repo)

    payload = service.create_context_payload(actor_username="actor@example.com")

    field = payload["form"]["fields"]["asp_group"]
    assert field["display_type"] == "select"
    assert field["options"] == list(ASP_GROUP_OPTIONS)
    assert payload["form"]["fields"]["asp_family"]["options"] == list(ASP_FAMILY_OPTIONS)
    assert payload["form"]["fields"]["asp_category"]["options"] == list(ASP_CATEGORY_OPTIONS)
    assert payload["form"]["fields"]["platform"]["options"] == list(PLATFORM_OPTIONS)
    assert payload["form"]["fields"]["expected_files"]["category_options"] == {
        key: list(values) for key, values in SAMPLE_FILE_KEYS.items()
    }
    assert payload["form"]["fields"]["required_files"]["category_options"] == {
        key: list(values) for key, values in SAMPLE_FILE_KEYS.items()
    }


def test_admin_panel_service_edit_context_keeps_current_asp_group_selected(monkeypatch):
    """ASP edit-context should preselect the panel's current assay group."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _asp_service(repo)

    payload = service.context_payload(panel_id="WGS")

    field = payload["form"]["fields"]["asp_group"]
    assert field["display_type"] == "select"
    assert field["default"] == payload["panel"]["asp_group"]
    assert field["options"] == list(ASP_GROUP_OPTIONS)


def test_admin_genelist_service_view_context_filters_genes(monkeypatch):
    """Test admin genelist service view context filters genes.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _isgl_service(repo)

    payload = service.view_context_payload(genelist_id="GL1", assay="WGS")

    assert payload["filtered_genes"] == ["TP53"]
    assert payload["panel_germline_genes"] == ["BRCA1"]


def test_admin_genelist_form_filters_asps_by_selected_groups(monkeypatch):
    """ISGL forms expose active ASP choices under their owning assay groups."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _isgl_service(repo)
    service.assay_panel_repository.get_all_asps = lambda is_active=None: [
        {"asp_id": "hema_gmsv1", "display_name": "Hematology GMSv1", "asp_group": "hematology"},
        {"asp_id": "solid_gmsv3", "display_name": "Solid DNA GMSv3", "asp_group": "solid"},
    ]

    payload = service.create_context_payload(actor_username="actor@example.com")
    form = payload["form"]

    assert "subpanel_id" not in form["fields"]
    assert form["fields"]["diagnosis"]["label"] == "Diagnosis / Subpanel IDs"
    assert form["fields"]["asp_ids"]["options_by_field"] == {
        "field": "asp_groups",
        "values": {
            "hematology": [
                {
                    "value": "hema_gmsv1",
                    "label": "Hematology GMSv1",
                    "category": "hematology",
                }
            ],
            "solid": [
                {
                    "value": "solid_gmsv3",
                    "label": "Solid DNA GMSv3",
                    "category": "solid",
                }
            ],
        },
    }


def test_admin_genelist_rejects_asp_outside_selected_groups(monkeypatch):
    """Direct API writes cannot bypass the dependent ASP-group selection."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _isgl_service(repo)
    service.assay_panel_repository.get_all_asps = lambda is_active=None: [
        {"asp_id": "hema_gmsv1", "asp_group": "hematology"},
        {"asp_id": "solid_gmsv3", "asp_group": "solid"},
    ]

    with pytest.raises(AppError) as exc_info:
        service.create(
            payload={
                "config": {
                    "isgl_id": "missing",
                    "name": "Solid scope",
                    "displayname": "Solid scope",
                    "list_type": ["snv"],
                    "asp_groups": ["solid"],
                    "asp_ids": ["hema_gmsv1"],
                }
            }
        )

    assert exc_info.value.status_code == 400
    assert "selected assay groups" in exc_info.value.message


def test_admin_aspc_create_context_scopes_optional_genelist_fields(monkeypatch):
    """ASPC forms expose optional ISGL choices scoped to the selected ASP."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _aspc_service(repo)

    payload = service.create_context_payload(category="DNA", actor_username="actor@example.com")
    form = payload["form"]
    analysis_options = form["fields"]["analysis_types"]["options"]
    analysis_options_by_asp = form["fields"]["analysis_types"]["options_by_field"]
    subpanel_options_by_asp = form["fields"]["subpanel_id"]["options_by_field"]
    filter_groups = form["fields"]["filters"]["groups"]
    reporting_groups = form["fields"]["reporting"]["groups"]
    filter_keys = {field["key"] for group in filter_groups for field in group.get("fields", [])}
    report_section_options = reporting_groups[0]["fields"][0]["options"]
    reporting_field_keys = {
        field["key"] for group in reporting_groups for field in group.get("fields", [])
    }

    assert "TMB" in analysis_options
    assert "PGX" in analysis_options
    assert analysis_options_by_asp["field"] == "asp_id"
    assert "SNV" in analysis_options_by_asp["values"]["wgs"]
    assert subpanel_options_by_asp["field"] == "asp_id"
    assert subpanel_options_by_asp["values"]["wgs"][0] == "base"
    assert "somatic.snv.snvlists" in filter_keys
    assert "somatic.cnv.cnvlists" in filter_keys
    assert "somatic.fusion.fusionlists" not in filter_keys
    assert "somatic.translocation.fusionlists" in filter_keys
    snv_list_field = next(
        field
        for group in filter_groups
        for field in group.get("fields", [])
        if field["key"] == "somatic.snv.snvlists"
    )
    assert snv_list_field["options_by_field"]["field"] == "asp_id"
    assert snv_list_field["options_by_field"]["values"]["wgs"] == []
    assert "TMB" in report_section_options
    assert "PGX" in report_section_options
    assert "report_sections" in reporting_field_keys
    assert "analysis" not in reporting_field_keys
    assert "general_report_summary" in reporting_field_keys


def test_admin_aspc_analysis_types_follow_the_asp_sequencing_family():
    """Targeted RNA panels reject WTS-only capabilities while WTS accepts them."""
    with pytest.raises(AppError) as exc_info:
        AspcService._validate_analysis_types_for_panel(
            {"analysis_types": ["FUSION", "EXPRESSION"]},
            {"asp_family": "panel-rna"},
        )

    assert exc_info.value.status_code == 400
    assert "EXPRESSION" in exc_info.value.message

    AspcService._validate_analysis_types_for_panel(
        {"analysis_types": ["FUSION", "EXPRESSION", "CLASSIFICATION", "QC"]},
        {"asp_family": "wts"},
    )

    assert AspcService._analysis_types_for_panel({"asp_family": "panel-rna"}, category="RNA") == [
        "FUSION",
        "QC",
        "PGX",
    ]
    assert "EXPRESSION" in AspcService._analysis_types_for_panel(
        {"asp_family": "wts"}, category="RNA"
    )


def test_admin_aspc_service_create_rejects_duplicate(monkeypatch):
    """Test admin aspc service create rejects duplicate.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _aspc_service(repo)

    with pytest.raises(AppError) as exc:
        service.create(payload={"config": {"aspc_id": "WGS:prod"}})

    assert exc.value.status_code == 409


def test_admin_sample_service_update_restores_ids(monkeypatch):
    """Test admin sample service update restores ids.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _resource_sample_service(repo)
    monkeypatch.setattr("api.application.resources.sample.current_actor", lambda username: username)
    monkeypatch.setattr(
        "api.application.resources.sample.utc_now", lambda: datetime.now(timezone.utc)
    )
    payload = service.update(
        sample_id="S1",
        payload={
            "sample": {
                "name": "CASE_1",
                "asp_id": "hema_gmsv1",
                "subpanel_id": "base",
                "environment": "production",
                "case_id": "CASE_1",
                "sample_no": 1,
                "sequencing_scope": "panel",
                "omics_layer": "dna",
                "pipeline": "test_pipeline",
                "pipeline_version": "1.0",
                "files": {"vcf_files": {"path": "/data/test.vcf"}},
                "field": "value",
            }
        },
        actor_username="actor@example.com",
    )

    assert payload["resource"] == "sample"
    assert payload["resource_id"] == "S1"
    assert payload["meta"]["sample_name"] == "CASE_1"
    assert payload["meta"]["sample_oid"] == "S1"
    assert repo.updated_sample_doc[0] == "S1"
