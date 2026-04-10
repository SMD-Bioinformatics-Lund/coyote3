"""Unit tests for admin workflow services."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import api.services.accounts.permissions as admin_permission_service_module
import api.services.accounts.roles as admin_role_service_module
import api.services.accounts.users as admin_user_service_module
import api.services.resources.asp as admin_asp_service_module
import api.services.resources.aspc as admin_aspc_service_module
import api.services.resources.isgl as admin_isgl_service_module
import api.services.resources.sample as admin_resource_service_module
from api.extensions import util as shared_util
from api.services.accounts.permissions import PermissionManagementService
from api.services.accounts.roles import RoleManagementService
from api.services.accounts.users import UserManagementService
from api.services.resources.asp import AspService
from api.services.resources.aspc import AspcService
from api.services.resources.isgl import IsglService
from api.services.resources.sample import ResourceSampleService


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
        return {"admin": {"permissions": ["perm.a"], "deny_permissions": [], "level": 99}}

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
            "roles": ["admin"],
            "password": "hashed",
            "version": 3,
            "permissions": [],
            "deny_permissions": [],
            "assay_groups": [],
            "assays": [],
            "auth_type": "coyote3",
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
    def user_handler(self):
        """User handler.

        Returns:
            The function result.
        """
        return type(
            "_UserHandler",
            (),
            {
                "user_exists": staticmethod(
                    lambda **kwargs: kwargs.get("user_id") == "taken"
                    or kwargs.get("email") == "taken@example.com"
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
            "deny_permissions": [],
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
                "_id": "perm.read",
                "permission_id": "perm.read",
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
                    "_id": "perm.read",
                    "permission_id": "perm.read",
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
        if permission_id in {"missing", "perm.create"}:
            return None
        return {
            "_id": permission_id,
            "permission_id": permission_id,
            "permission_name": permission_id,
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
                "assays": ["WGS"],
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
            "assays": ["WGS"],
            "assay_groups": ["dna"],
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

    def list_samples_for_admin(self, *, assays, search, page=1, per_page=30):
        """List samples for admin.

        Args:
            assays: Value for ``assays``.
            search: Value for ``search``.

        Returns:
            The function result.
        """
        _ = (assays, search, page, per_page)
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
        user_handler=SimpleNamespace(
            search_users=repo.search_users,
            user_with_id=repo.get_user,
            create_user=repo.create_user,
            update_user=repo.update_user,
            toggle_user_active=repo.set_user_active,
            delete_user=repo.delete_user,
            user_exists=repo.user_handler.user_exists,
        ),
        roles_handler=SimpleNamespace(
            search_roles=repo.search_roles,
            get_role_colors=repo.get_role_colors,
            get_all_role_names=repo.get_role_names,
            get_all_roles=lambda: [
                {
                    "role_id": role_id,
                    "permissions": role_data.get("permissions", []),
                    "deny_permissions": role_data.get("deny_permissions", []),
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
        permissions_handler=SimpleNamespace(
            search_permissions=repo.search_permissions,
            get_all_permissions=repo.list_permissions,
            get_permission=repo.get_permission,
            create_new_policy=repo.create_permission,
            update_policy=repo.update_permission,
            toggle_policy_active=repo.set_permission_active,
            delete_policy=repo.delete_permission,
        ),
        vep_metadata_handler=SimpleNamespace(
            get_consequence_group_options=lambda vep=None: ["missense", "splicing"],
        ),
        assay_panel_handler=SimpleNamespace(
            search_asps=repo.search_panels,
            get_all_asp_groups=repo.get_asp_groups,
            get_all_asps=lambda is_active=None: [repo.get_panel("WGS")],
            get_asp=repo.get_panel,
            create_panel=repo.create_panel,
            update_asp=repo.update_panel,
            toggle_asp_active=repo.set_panel_active,
            delete_panel=repo.delete_panel,
        ),
        gene_list_handler=SimpleNamespace(
            search_isgls=repo.search_genelists,
            get_all_isgl=repo.list_genelists,
            get_isgl=repo.get_genelist,
            create_genelist=repo.create_genelist,
            update_isgl=repo.update_genelist,
            toggle_isgl_active=repo.set_genelist_active,
            delete_genelist=repo.delete_genelist,
        ),
        assay_configuration_handler=SimpleNamespace(
            search_aspcs=repo.search_assay_configs,
            get_aspc=repo.get_assay_config,
            get_aspc_with_id=repo.get_assay_config,
            get_available_assay_envs=repo.get_available_assay_envs,
            create_assay_config=repo.create_assay_config,
            update_aspc=repo.update_assay_config,
            toggle_aspc_active=repo.set_assay_config_active,
            delete_assay_config=repo.delete_assay_config,
        ),
        sample_handler=SimpleNamespace(
            search_samples_for_admin=repo.list_samples_for_admin,
            get_sample=repo.get_sample,
            update_sample=repo.update_sample,
            get_sample_name=repo.get_sample_name,
        ),
        variant_handler=SimpleNamespace(),
        copy_number_variant_handler=SimpleNamespace(),
        coverage_handler=SimpleNamespace(),
        translocation_handler=SimpleNamespace(),
        fusion_handler=SimpleNamespace(),
        biomarker_handler=SimpleNamespace(),
    )


def _user_service(repo: _AdminRepoStub) -> UserManagementService:
    store = _build_store(repo)
    return UserManagementService(
        user_handler=store.user_handler,
        roles_handler=store.roles_handler,
        permissions_handler=store.permissions_handler,
        assay_panel_handler=store.assay_panel_handler,
        common_util=shared_util.common,
    )


def _role_service(repo: _AdminRepoStub) -> RoleManagementService:
    store = _build_store(repo)
    return RoleManagementService(
        roles_handler=store.roles_handler,
        permissions_handler=store.permissions_handler,
    )


def _permission_service(repo: _AdminRepoStub) -> PermissionManagementService:
    store = _build_store(repo)
    return PermissionManagementService(permissions_handler=store.permissions_handler)


def _asp_service(repo: _AdminRepoStub) -> AspService:
    store = _build_store(repo)
    return AspService(assay_panel_handler=store.assay_panel_handler)


def _isgl_service(repo: _AdminRepoStub) -> IsglService:
    store = _build_store(repo)
    return IsglService(
        gene_list_handler=store.gene_list_handler, assay_panel_handler=store.assay_panel_handler
    )


def _aspc_service(repo: _AdminRepoStub) -> AspcService:
    store = _build_store(repo)
    return AspcService(
        assay_configuration_handler=store.assay_configuration_handler,
        assay_panel_handler=store.assay_panel_handler,
        vep_metadata_handler=store.vep_metadata_handler,
        common_util=shared_util.common,
    )


def _resource_sample_service(repo: _AdminRepoStub) -> ResourceSampleService:
    store = _build_store(repo)
    return ResourceSampleService(
        sample_handler=store.sample_handler,
        variant_handler=store.variant_handler,
        copy_number_variant_handler=store.copy_number_variant_handler,
        coverage_handler=store.coverage_handler,
        translocation_handler=store.translocation_handler,
        fusion_handler=store.fusion_handler,
        biomarker_handler=store.biomarker_handler,
        records_util=shared_util.records,
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
    monkeypatch.setattr("api.services.accounts.users.current_actor", lambda username: username)
    monkeypatch.setattr(
        "api.services.accounts.users.inject_version_history",
        lambda **kwargs: kwargs["new_config"],
    )
    monkeypatch.setattr("api.services.accounts.users.utc_now", lambda: datetime.now(timezone.utc))
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
                "permissions": form_data.get("permissions", []),
                "deny_permissions": form_data.get("deny_permissions", []),
                "auth_type": "coyote3",
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
        user_handler=service.user_handler,
        roles_handler=service.roles_handler,
        permissions_handler=service.permissions_handler,
        assay_panel_handler=service.assay_panel_handler,
        common_util=shared_util.common,
    )

    payload = service.create_user(
        payload={
            "form_data": {
                "username": "NewTester",
                "email": "NewTester@Example.com",
                "roles": ["admin"],
                "permissions": ["perm.a", "perm.b"],
            }
        },
        actor_username="actor@example.com",
    )

    assert payload["resource"] == "user"
    assert repo.created_user["username"] == "newtester"
    assert repo.created_user["email"] == "newtester@example.com"
    assert repo.created_user["password"] == "H:secret"
    assert repo.created_user["permissions"] == ["perm.b"]


def test_admin_user_service_toggle_user_sets_status(monkeypatch):
    """Test admin user service toggle user sets status.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _user_service(repo)

    payload = service.toggle_user(user_id="tester")

    assert payload["meta"]["is_active"] is True
    assert repo.updated_user == ("tester", {"is_active": True})


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
    monkeypatch.setattr("api.services.accounts.roles.current_actor", lambda username: username)
    monkeypatch.setattr(
        "api.services.accounts.roles.inject_version_history",
        lambda **kwargs: kwargs["new_config"],
    )
    monkeypatch.setattr(
        admin_role_service_module,
        "normalize_managed_form_payload",
        lambda _spec, form_data: {
            "name": form_data["name"],
            "label": form_data.get("name", ""),
            "color": "#1f2937",
            "permissions": [],
            "deny_permissions": [],
        },
    )

    payload = service.create_role(
        payload={"form_data": {"name": "Developer"}}, actor_username="actor@example.com"
    )

    assert payload["resource"] == "role"
    assert repo.created_role["role_id"] == "developer"
    assert repo.created_role["name"] == "Developer"
    assert repo.created_role["level"] == 9999


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


def test_admin_permission_service_groups_permissions(monkeypatch):
    """Test admin permission service groups permissions.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _permission_service(repo)

    payload = service.list_permissions_payload()

    assert payload["permission_policies"][0]["permission_id"] == "perm.read"
    assert "General" in payload["grouped_permissions"]


def test_admin_permission_service_create_context_uses_backend_contract_form(monkeypatch):
    """Permission create-context should be served from the backend contract form."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _permission_service(repo)

    payload = service.create_context_payload(actor_username="actor@example.com")

    assert payload["form"]["form_type"] == "permission"
    assert payload["form"]["fields"]["created_by"]["default"] == "actor@example.com"


def test_admin_permission_service_toggle_permission_sets_status(monkeypatch):
    """Test admin permission service toggle permission sets status.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _permission_service(repo)

    payload = service.toggle_permission(permission_id="perm.read")

    assert payload["meta"]["is_active"] is False
    assert repo.updated_permission == ("perm.read", {"is_active": False})


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


def test_admin_aspc_create_context_uses_analysis_sections_not_genelist_fields(monkeypatch):
    """ASPC form should expose analysis/report toggles, not sample-owned gene-list selectors."""
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _aspc_service(repo)

    payload = service.create_context_payload(category="DNA", actor_username="actor@example.com")
    form = payload["form"]
    analysis_options = form["fields"]["analysis_types"]["options"]
    filter_groups = form["fields"]["filters"]["groups"]
    reporting_groups = form["fields"]["reporting"]["groups"]
    filter_keys = {field["key"] for group in filter_groups for field in group.get("fields", [])}
    report_section_options = reporting_groups[0]["fields"][0]["options"]

    assert "TMB" in analysis_options
    assert "PGX" in analysis_options
    assert "genelists" not in filter_keys
    assert "cnv_genelists" not in filter_keys
    assert "fusion_genelists" not in filter_keys
    assert "TMB" in report_section_options
    assert "PGX" in report_section_options


def test_admin_aspc_service_create_rejects_duplicate(monkeypatch):
    """Test admin aspc service create rejects duplicate.

    Returns:
        The function result.
    """
    repo = _AdminRepoStub()
    _patch_admin_stores(monkeypatch, repo)
    service = _aspc_service(repo)

    with pytest.raises(HTTPException) as exc:
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
    monkeypatch.setattr("api.services.resources.sample.current_actor", lambda username: username)
    monkeypatch.setattr("api.services.resources.sample.utc_now", lambda: datetime.now(timezone.utc))
    service.records_util = SimpleNamespace(restore_object_ids=lambda payload: payload)

    payload = service.update(
        sample_id="S1", payload={"sample": {"field": "value"}}, actor_username="actor@example.com"
    )

    assert payload["resource"] == "sample"
    assert repo.updated_sample_doc[0] == "S1"
