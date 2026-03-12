"""Unit tests for admin workflow services."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.services.admin_permission_service import AdminPermissionService
from api.services.admin_resource_service import (
    AdminAspcService,
    AdminGenelistService,
    AdminPanelService,
    AdminSampleService,
    AdminSchemaService,
)
from api.services.admin_role_service import AdminRoleService
from api.services.admin_user_service import AdminUserService


class _AdminRepoStub:
    def __init__(self) -> None:
        self.created_user = None
        self.updated_user = None
        self.created_role = None
        self.updated_role = None
        self.deleted_users: list[str] = []
        self.deleted_roles: list[str] = []

    def list_users(self):
        return [{"_id": "tester", "user_id": "tester"}]

    def get_role_colors(self):
        return {"admin": "#000"}

    def get_active_schema(self, **kwargs):
        return (
            [{"_id": "schema1", "schema_id": "schema1", "version": 2, "fields": {"role": {}, "permissions": {}, "deny_permissions": {}, "assay_groups": {}, "created_by": {}, "created_on": {}, "updated_by": {}, "updated_on": {}}}],
            {"_id": "schema1", "schema_id": "schema1", "version": 2, "fields": {"role": {}, "permissions": {}, "deny_permissions": {}, "assay_groups": {}, "created_by": {}, "created_on": {}, "updated_by": {}, "updated_on": {}}},
        )

    def clone_schema(self, schema):
        return {
            "_id": schema["_id"],
            "schema_id": schema["schema_id"],
            "version": schema["version"],
            "fields": {k: dict(v) for k, v in schema["fields"].items()},
        }

    def list_permission_policy_options(self):
        return [{"value": "perm.a", "label": "perm.a", "category": "General"}]

    def get_role_names(self):
        return ["admin"]

    def get_roles_policy_map(self):
        return {"admin": {"permissions": ["perm.a"], "deny_permissions": [], "level": 99}}

    def get_assay_group_map(self):
        return {"dna": [{"_id": "WGS"}]}

    def get_asp_groups(self):
        return ["dna"]

    def create_user(self, user_data):
        self.created_user = user_data

    def get_user(self, user_id):
        if user_id == "missing":
            return None
        return {
            "_id": "tester",
            "user_id": "tester",
            "username": "tester",
            "email": "tester@example.com",
            "schema_name": "schema1",
            "role": "admin",
            "password": "hashed",
            "version": 3,
            "permissions": [],
            "deny_permissions": [],
            "assay_groups": [],
            "assays": [],
            "auth_type": "coyote3",
        }

    def get_schema(self, schema_name):
        if not schema_name:
            return None
        return {"_id": "schema1", "schema_id": "schema1", "version": 2, "fields": {"role": {}, "permissions": {}, "deny_permissions": {}, "assay_groups": {}, "assays": {}}}

    def update_user(self, user_id, user_data):
        self.updated_user = (user_id, user_data)

    def delete_user(self, user_id):
        self.deleted_users.append(user_id)

    def set_user_active(self, user_id, is_active):
        self.updated_user = (user_id, {"is_active": is_active})

    @property
    def user_handler(self):
        return type(
            "_UserHandler",
            (),
            {
                "user_exists": staticmethod(lambda **kwargs: kwargs.get("user_id") == "taken" or kwargs.get("email") == "taken@example.com")
            },
        )()

    def list_roles(self):
        return [{"_id": "admin", "role_id": "admin", "level": 99}]

    def get_role(self, role_id):
        if role_id == "missing":
            return None
        return {
            "_id": "admin",
            "role_id": "admin",
            "name": "Admin",
            "schema_name": "schema1",
            "permissions": [],
            "deny_permissions": [],
            "version": 4,
        }

    def create_role(self, role_data):
        self.created_role = role_data

    def update_role(self, role_id, role_data):
        self.updated_role = (role_id, role_data)

    def set_role_active(self, role_id, is_active):
        self.updated_role = (role_id, {"is_active": is_active})

    def delete_role(self, role_id):
        self.deleted_roles.append(role_id)

    def list_permissions(self, *, is_active=False):
        return [{"_id": "perm.read", "permission_id": "perm.read", "category": "General", "is_active": True}]

    def get_permission(self, permission_id):
        if permission_id == "missing":
            return None
        return {
            "_id": permission_id,
            "permission_id": permission_id,
            "permission_name": permission_id,
            "schema_name": "schema1",
            "version": 4,
            "is_active": True,
            "category": "General",
        }

    def create_permission(self, policy):
        self.created_permission = policy

    def update_permission(self, permission_id, policy):
        self.updated_permission = (permission_id, policy)

    def set_permission_active(self, permission_id, is_active):
        self.updated_permission = (permission_id, {"is_active": is_active})

    def delete_permission(self, permission_id):
        self.deleted_permissions = getattr(self, "deleted_permissions", [])
        self.deleted_permissions.append(permission_id)

    def list_panels(self, *, is_active=None):
        return [{"_id": "WGS", "asp_id": "WGS", "schema_name": "ASP-Schema"}]

    def get_panel(self, panel_id):
        if panel_id == "missing":
            return None
        return {"_id": panel_id, "asp_id": panel_id, "schema_name": "ASP-Schema", "is_active": False, "covered_genes": ["TP53"], "germline_genes": ["BRCA1"]}

    def create_panel(self, panel):
        self.created_panel = panel

    def update_panel(self, panel_id, panel):
        self.updated_panel = (panel_id, panel)

    def set_panel_active(self, panel_id, is_active):
        self.updated_panel = (panel_id, {"is_active": is_active})

    def delete_panel(self, panel_id):
        self.deleted_panels = getattr(self, "deleted_panels", [])
        self.deleted_panels.append(panel_id)

    def list_genelists(self):
        return [{"_id": "GL1", "isgl_id": "GL1", "schema_name": "schema1", "genes": ["TP53"], "assays": ["WGS"]}]

    def get_genelist(self, genelist_id):
        if genelist_id == "missing":
            return None
        return {"_id": genelist_id, "isgl_id": genelist_id, "schema_name": "schema1", "genes": ["TP53", "EGFR"], "assays": ["WGS"], "assay_groups": ["dna"], "is_active": True}

    def create_genelist(self, genelist):
        self.created_genelist = genelist

    def update_genelist(self, genelist_id, genelist):
        self.updated_genelist = (genelist_id, genelist)

    def set_genelist_active(self, genelist_id, is_active):
        self.updated_genelist = (genelist_id, {"is_active": is_active})

    def delete_genelist(self, genelist_id):
        self.deleted_genelists = getattr(self, "deleted_genelists", [])
        self.deleted_genelists.append(genelist_id)

    def list_assay_configs(self):
        return [{"_id": "WGS:prod", "aspc_id": "WGS:prod", "schema_name": "schema1"}]

    def get_assay_config(self, assay_id):
        if assay_id == "missing":
            return None
        return {"_id": assay_id, "aspc_id": assay_id, "schema_name": "schema1", "is_active": True}

    def create_assay_config(self, config):
        self.created_aspc = config

    def update_assay_config(self, assay_id, config):
        self.updated_aspc = (assay_id, config)

    def set_assay_config_active(self, assay_id, is_active):
        self.updated_aspc = (assay_id, {"is_active": is_active})

    def delete_assay_config(self, assay_id):
        self.deleted_aspc = getattr(self, "deleted_aspc", [])
        self.deleted_aspc.append(assay_id)

    def get_available_assay_envs(self, assay_id, allowed_envs):
        return ["production"]

    def list_samples_for_admin(self, *, assays, search):
        return [{"_id": "S1"}]

    def get_sample(self, sample_id):
        if sample_id == "missing":
            return None
        return {"_id": sample_id, "sample_id": sample_id}

    def update_sample(self, sample_obj, updated_sample):
        self.updated_sample_doc = (sample_obj, updated_sample)

    def get_sample_name(self, sample_id):
        if sample_id == "missing":
            return None
        return sample_id

    def list_schemas(self):
        return [{"_id": "schema1"}]

    def create_schema(self, schema_doc):
        self.created_schema = schema_doc

    def update_schema(self, schema_id, schema_doc):
        self.updated_schema = (schema_id, schema_doc)

    def set_schema_active(self, schema_id, is_active):
        self.updated_schema = (schema_id, {"is_active": is_active})

    def delete_schema(self, schema_id):
        self.deleted_schemas = getattr(self, "deleted_schemas", [])
        self.deleted_schemas.append(schema_id)


def test_admin_user_service_create_user_normalizes_identity(monkeypatch):
    repo = _AdminRepoStub()
    service = AdminUserService(repository=repo)
    monkeypatch.setattr("api.services.admin_user_service.current_actor", lambda username: username)
    monkeypatch.setattr("api.services.admin_user_service.inject_version_history", lambda **kwargs: kwargs["new_config"])
    monkeypatch.setattr("api.services.admin_user_service.utc_now", lambda: "NOW")
    monkeypatch.setattr(
        "api.services.admin_user_service.util.admin.process_form_to_config",
        lambda form_data, schema: {
            "username": form_data["username"],
            "email": form_data["email"],
            "role": form_data["role"],
            "permissions": form_data.get("permissions", []),
            "deny_permissions": form_data.get("deny_permissions", []),
            "auth_type": "coyote3",
            "password": "secret",
        },
    )
    monkeypatch.setattr("api.services.admin_user_service.util.common.hash_password", lambda raw: f"H:{raw}")

    payload = service.create_user(
        payload={"form_data": {"username": "Tester", "email": "Tester@Example.com", "role": "admin", "permissions": ["perm.a", "perm.b"]}},
        actor_username="actor@example.com",
    )

    assert payload["resource"] == "user"
    assert repo.created_user["user_id"] == "tester"
    assert repo.created_user["_id"] == "tester"
    assert repo.created_user["email"] == "tester@example.com"
    assert repo.created_user["password"] == "H:secret"
    assert repo.created_user["permissions"] == ["perm.b"]


def test_admin_user_service_toggle_user_sets_status():
    repo = _AdminRepoStub()
    service = AdminUserService(repository=repo)

    payload = service.toggle_user(user_id="tester")

    assert payload["meta"]["is_active"] is True
    assert repo.updated_user == ("tester", {"is_active": True})


def test_admin_role_service_create_role_normalizes_business_key(monkeypatch):
    repo = _AdminRepoStub()
    service = AdminRoleService(repository=repo)
    monkeypatch.setattr("api.services.admin_role_service.current_actor", lambda username: username)
    monkeypatch.setattr("api.services.admin_role_service.inject_version_history", lambda **kwargs: kwargs["new_config"])
    monkeypatch.setattr(
        "api.services.admin_role_service.util.admin.process_form_to_config",
        lambda form_data, schema: {"name": form_data["name"], "permissions": [], "deny_permissions": []},
    )

    payload = service.create_role(payload={"form_data": {"name": "Admin"}}, actor_username="actor@example.com")

    assert payload["resource"] == "role"
    assert repo.created_role["role_id"] == "admin"
    assert repo.created_role["_id"] == "admin"


def test_admin_role_service_delete_role_removes_existing_role():
    repo = _AdminRepoStub()
    service = AdminRoleService(repository=repo)

    payload = service.delete_role(role_id="admin")

    assert payload["action"] == "delete"
    assert repo.deleted_roles == ["admin"]


def test_admin_permission_service_groups_permissions():
    repo = _AdminRepoStub()
    service = AdminPermissionService(repository=repo)

    payload = service.list_permissions_payload()

    assert payload["permission_policies"][0]["permission_id"] == "perm.read"
    assert "General" in payload["grouped_permissions"]


def test_admin_permission_service_create_context_raises_when_missing_schema():
    repo = _AdminRepoStub()
    repo.get_active_schema = lambda **kwargs: ([], {})
    service = AdminPermissionService(repository=repo)

    with pytest.raises(HTTPException) as exc:
        service.create_context_payload(schema_id=None, actor_username="actor@example.com")

    assert exc.value.status_code == 400


def test_admin_permission_service_toggle_permission_sets_status():
    repo = _AdminRepoStub()
    service = AdminPermissionService(repository=repo)

    payload = service.toggle_permission(permission_id="perm.read")

    assert payload["meta"]["is_active"] is False
    assert repo.updated_permission == ("perm.read", {"is_active": False})


def test_admin_panel_service_toggle_panel_sets_status():
    repo = _AdminRepoStub()
    service = AdminPanelService(repository=repo)

    payload = service.toggle(panel_id="WGS")

    assert payload["meta"]["is_active"] is True
    assert repo.updated_panel == ("WGS", {"is_active": True})


def test_admin_genelist_service_view_context_filters_genes():
    repo = _AdminRepoStub()
    service = AdminGenelistService(repository=repo)

    payload = service.view_context_payload(genelist_id="GL1", assay="WGS")

    assert payload["filtered_genes"] == ["TP53"]
    assert payload["panel_germline_genes"] == ["BRCA1"]


def test_admin_aspc_service_create_rejects_duplicate():
    repo = _AdminRepoStub()
    service = AdminAspcService(repository=repo)

    with pytest.raises(HTTPException) as exc:
        service.create(payload={"config": {"aspc_id": "WGS:prod"}})

    assert exc.value.status_code == 409


def test_admin_schema_service_create_sets_identity(monkeypatch):
    repo = _AdminRepoStub()
    service = AdminSchemaService(repository=repo)
    monkeypatch.setattr("api.services.admin_resource_service.current_actor", lambda username: username)
    monkeypatch.setattr("api.services.admin_resource_service.utc_now", lambda: "NOW")

    payload = service.create(payload={"schema": {"schema_name": "USER-SCHEMA"}}, actor_username="actor@example.com")

    assert payload["resource"] == "schema"
    assert repo.created_schema["schema_id"] == "USER-SCHEMA"


def test_admin_sample_service_update_restores_ids(monkeypatch):
    repo = _AdminRepoStub()
    service = AdminSampleService(repository=repo)
    monkeypatch.setattr("api.services.admin_resource_service.current_actor", lambda username: username)
    monkeypatch.setattr("api.services.admin_resource_service.utc_now", lambda: "NOW")
    monkeypatch.setattr("api.services.admin_resource_service.util.admin.restore_objectids", lambda payload: payload)

    payload = service.update(sample_id="S1", payload={"sample": {"field": "value"}}, actor_username="actor@example.com")

    assert payload["resource"] == "sample"
    assert repo.updated_sample_doc[0] == "S1"
