"""Additional unit tests for admin service workflows."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import api.services.admin_role_service as role_module
import api.services.admin_user_service as user_module
import api.services.permission_management_service as perm_module
from api.services.admin_role_service import AdminRoleService
from api.services.admin_user_service import AdminUserService
from api.services.permission_management_service import PermissionManagementService


class _Repo:
    def __init__(self) -> None:
        self.updated_user = None
        self.updated_role = None
        self.updated_permission = None
        self.created_permission = None
        self.deleted_permission = []
        self.deleted_user = []
        self.deleted_role = []

    def search_users(self, *, q="", page=1, per_page=30):
        _ = (q, page, per_page)
        return ([{"_id": "u1"}], 1)

    def search_roles(self, *, q="", page=1, per_page=30):
        _ = (q, page, per_page)
        return ([{"_id": "r1"}], 1)

    def search_permissions(self, *, q="", page=1, per_page=30, is_active=False):
        _ = (q, page, per_page, is_active)
        return ([{"_id": "p1", "permission_id": "perm.read", "category": "General"}], 1)

    def get_role_colors(self):
        return {}

    def get_active_schema(self, **kwargs):
        _ = kwargs
        schema = {
            "_id": "schema1",
            "schema_id": "schema1",
            "version": 1,
            "fields": {
                "role": {},
                "permissions": {},
                "deny_permissions": {},
                "assay_groups": {},
                "assays": {},
                "created_by": {},
                "created_on": {},
                "updated_by": {},
                "updated_on": {},
            },
        }
        return [schema], schema

    def clone_schema(self, schema):
        return {"fields": {k: dict(v) for k, v in schema["fields"].items()}, **schema}

    def get_asp_groups(self):
        return ["dna"]

    def get_roles_policy_map(self):
        return {"admin": {"permissions": ["perm.read"], "deny_permissions": []}}

    def get_assay_group_map(self):
        return {"dna": ["WGS"]}

    def list_permission_policy_options(self):
        return [{"value": "perm.read"}]

    def get_role_names(self):
        return ["admin"]

    def get_user(self, user_id):
        if user_id == "missing":
            return None
        return {
            "_id": "oid-1",
            "user_id": user_id,
            "username": user_id,
            "email": f"{user_id}@example.com",
            "schema_name": "schema1",
            "auth_type": "coyote3",
            "password": "hashed",
            "version": 1,
            "permissions": [],
            "deny_permissions": [],
            "assay_groups": [],
            "assays": [],
            "is_active": False,
        }

    def get_role(self, role_id):
        if role_id == "missing":
            return None
        return {
            "_id": "oid-role",
            "role_id": role_id,
            "schema_name": "schema1",
            "version": 1,
            "permissions": [],
            "deny_permissions": [],
            "is_active": False,
        }

    def get_permission(self, permission_id):
        if permission_id == "missing":
            return None
        return {
            "_id": "oid-perm",
            "permission_id": permission_id,
            "permission_name": permission_id,
            "schema_name": "schema1",
            "version": 1,
            "is_active": True,
        }

    def get_schema(self, schema_name):
        if schema_name == "missing":
            return None
        return {
            "_id": "schema1",
            "schema_id": "schema1",
            "version": 2,
            "fields": {
                "permissions": {},
                "deny_permissions": {},
                "role": {},
                "assay_groups": {},
                "assays": {},
            },
        }

    def update_user(self, user_id, doc):
        self.updated_user = (user_id, doc)

    def update_role(self, role_id, doc):
        self.updated_role = (role_id, doc)

    def update_permission(self, permission_id, doc):
        self.updated_permission = (permission_id, doc)

    def set_user_active(self, user_id, is_active):
        self.updated_user = (user_id, is_active)

    def set_role_active(self, role_id, is_active):
        self.updated_role = (role_id, is_active)

    def set_permission_active(self, permission_id, is_active):
        self.updated_permission = (permission_id, is_active)

    def create_permission(self, doc):
        self.created_permission = doc

    def delete_permission(self, permission_id):
        self.deleted_permission.append(permission_id)

    def delete_user(self, user_id):
        self.deleted_user.append(user_id)

    def delete_role(self, role_id):
        self.deleted_role.append(role_id)

    @property
    def user_handler(self):
        return SimpleNamespace(user_exists=lambda **kwargs: kwargs.get("username") == "exists")


def test_admin_user_list_payload_contains_pagination():
    service = AdminUserService(repository=_Repo())
    payload = service.list_users_payload(q="aa", page=2, per_page=5)
    assert payload["pagination"]["page"] == 2
    assert payload["pagination"]["q"] == "aa"


def test_admin_role_list_payload_contains_pagination():
    service = AdminRoleService(repository=_Repo())
    payload = service.list_roles_payload(q="bb", page=3, per_page=7)
    assert payload["pagination"]["per_page"] == 7


def test_permission_list_payload_contains_pagination():
    service = PermissionManagementService(repository=_Repo())
    payload = service.list_permissions_payload(q="perm", page=2, per_page=10)
    assert payload["pagination"]["q"] == "perm"
    assert "General" in payload["grouped_permissions"]


def test_admin_user_update_preserves_password_when_blank(monkeypatch):
    repo = _Repo()
    service = AdminUserService(repository=repo)
    monkeypatch.setattr(user_module, "current_actor", lambda u: u)
    monkeypatch.setattr(user_module, "utc_now", lambda: "NOW")
    monkeypatch.setattr(
        user_module, "inject_version_history", lambda **kwargs: kwargs["new_config"]
    )
    monkeypatch.setattr(
        user_module.util,
        "admin",
        SimpleNamespace(
            process_form_to_config=lambda _form, _schema: {
                "username": "TESTER",
                "email": "TESTER@EXAMPLE.COM",
                "auth_type": "coyote3",
                "password": "",
                "role": "admin",
                "permissions": [],
                "deny_permissions": [],
            }
        ),
        raising=False,
    )

    payload = service.update_user(
        user_id="tester", payload={"form_data": {}}, actor_username="actor@example.com"
    )

    assert payload["action"] == "update"
    assert repo.updated_user[1]["password"] == "hashed"
    assert repo.updated_user[1]["username"] == "tester"
    assert repo.updated_user[1]["email"] == "tester@example.com"


def test_admin_user_update_raises_when_user_missing():
    service = AdminUserService(repository=_Repo())
    with pytest.raises(HTTPException) as exc:
        service.update_user(user_id="missing", payload={"form_data": {}}, actor_username="actor")
    assert exc.value.status_code == 404


def test_admin_user_context_raises_when_schema_missing():
    repo = _Repo()
    repo.get_user = lambda _user_id: {"schema_name": "missing"}
    service = AdminUserService(repository=repo)
    with pytest.raises(HTTPException) as exc:
        service.context_payload(user_id="u1")
    assert exc.value.status_code == 404


def test_admin_role_update_success(monkeypatch):
    repo = _Repo()
    service = AdminRoleService(repository=repo)
    monkeypatch.setattr(role_module, "current_actor", lambda u: u)
    monkeypatch.setattr(role_module, "utc_now", lambda: "NOW")
    monkeypatch.setattr(
        role_module, "inject_version_history", lambda **kwargs: kwargs["new_config"]
    )
    monkeypatch.setattr(
        role_module.util,
        "admin",
        SimpleNamespace(
            process_form_to_config=lambda _form, _schema: {"name": "Admin", "permissions": []}
        ),
        raising=False,
    )

    payload = service.update_role(
        role_id="admin", payload={"form_data": {}}, actor_username="actor"
    )

    assert payload["action"] == "update"
    assert repo.updated_role[1]["role_id"] == "admin"


def test_admin_role_update_raises_when_schema_missing():
    repo = _Repo()
    repo.get_schema = lambda _name: None
    service = AdminRoleService(repository=repo)
    with pytest.raises(HTTPException) as exc:
        service.update_role(role_id="admin", payload={"form_data": {}}, actor_username="actor")
    assert exc.value.status_code == 404


def test_permission_create_and_update_success(monkeypatch):
    repo = _Repo()
    service = PermissionManagementService(repository=repo)
    monkeypatch.setattr(perm_module, "current_actor", lambda u: u)
    monkeypatch.setattr(perm_module, "utc_now", lambda: "NOW")
    monkeypatch.setattr(
        perm_module, "inject_version_history", lambda **kwargs: kwargs["new_config"]
    )
    monkeypatch.setattr(
        perm_module.util,
        "admin",
        SimpleNamespace(
            process_form_to_config=lambda form_data, _schema: {
                "permission_name": form_data["permission_name"]
            }
        ),
        raising=False,
    )

    create_payload = service.create_permission(
        payload={"form_data": {"permission_name": "perm.create"}}, actor_username="actor"
    )
    update_payload = service.update_permission(
        permission_id="perm.read",
        payload={"form_data": {"permission_name": "perm.read"}},
        actor_username="actor",
    )

    assert create_payload["resource_id"] == "perm.create"
    assert repo.created_permission["permission_id"] == "perm.create"
    assert update_payload["action"] == "update"
    assert repo.updated_permission[1]["permission_id"] == "perm.read"


def test_permission_context_and_delete_paths():
    service = PermissionManagementService(repository=_Repo())
    payload = service.context_payload(permission_id="perm.read")
    deleted = service.delete_permission(permission_id="perm.read")
    assert payload["permission"]["permission_id"] == "perm.read"
    assert deleted["action"] == "delete"


def test_username_and_email_exists():
    service = AdminUserService(repository=_Repo())
    assert service.username_exists(username="exists")
    assert not service.email_exists(email="new@example.com")
