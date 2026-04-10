"""Additional unit tests for admin service workflows."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

import api.services.accounts.permissions as perm_module
import api.services.accounts.roles as role_module
import api.services.accounts.users as user_module
from api.extensions import util as shared_util
from api.services.accounts.permissions import PermissionManagementService
from api.services.accounts.roles import RoleManagementService
from api.services.accounts.users import UserManagementService


class _Repo:
    def __init__(self) -> None:
        self.created_user = None
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
        if user_id not in {"tester", "exists", "u1"}:
            return None
        return {
            "_id": "oid-1",
            "user_id": user_id,
            "username": user_id,
            "email": f"{user_id}@example.com",
            "firstname": "Test",
            "lastname": "User",
            "fullname": "Test User",
            "job_title": "Analyst",
            "auth_type": "coyote3",
            "password": "hashed",
            "version": 1,
            "roles": ["admin"],
            "permissions": [],
            "deny_permissions": [],
            "assay_groups": [],
            "assays": [],
            "is_active": False,
            "created_by": "seed",
            "created_on": datetime.now(timezone.utc),
        }

    def get_role(self, role_id):
        if role_id == "missing":
            return None
        return {
            "_id": "oid-role",
            "role_id": role_id,
            "name": role_id.title(),
            "label": role_id.title(),
            "color": "#1f2937",
            "level": 100,
            "version": 1,
            "permissions": [],
            "deny_permissions": [],
            "is_active": False,
        }

    def get_permission(self, permission_id):
        if permission_id in {"missing", "perm.create"}:
            return None
        return {
            "_id": "oid-perm",
            "permission_id": permission_id,
            "permission_name": permission_id,
            "label": permission_id,
            "category": "General",
            "tags": [],
            "version": 1,
            "is_active": True,
        }

    def update_user(self, user_id, doc):
        self.updated_user = (user_id, doc)

    def create_user(self, doc):
        self.created_user = doc

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


def _build_store(repo: _Repo) -> SimpleNamespace:
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
            get_all_roles=lambda: [repo.get_role("admin")],
            get_role=repo.get_role,
            update_role=repo.update_role,
            toggle_role_active=repo.set_role_active,
            delete_role=repo.delete_role,
        ),
        permissions_handler=SimpleNamespace(
            search_permissions=repo.search_permissions,
            get_all_permissions=lambda is_active=True: [
                {"permission_id": "perm.read", "category": "General"}
            ],
            get_permission=repo.get_permission,
            create_new_policy=repo.create_permission,
            update_policy=repo.update_permission,
            toggle_policy_active=repo.set_permission_active,
            delete_policy=repo.delete_permission,
        ),
        assay_panel_handler=SimpleNamespace(
            get_all_asp_groups=repo.get_asp_groups,
            get_all_asps=lambda is_active=None: [{"_id": "WGS", "asp_group": "dna"}],
        ),
    )


def _patch_admin_stores(monkeypatch, repo: _Repo) -> None:
    store = _build_store(repo)
    monkeypatch.setattr(user_module, "store", store, raising=False)
    monkeypatch.setattr(role_module, "store", store, raising=False)
    monkeypatch.setattr(perm_module, "store", store, raising=False)


def _user_service(repo: _Repo) -> UserManagementService:
    store = _build_store(repo)
    return UserManagementService(
        user_handler=store.user_handler,
        roles_handler=store.roles_handler,
        permissions_handler=store.permissions_handler,
        assay_panel_handler=store.assay_panel_handler,
        common_util=shared_util.common,
    )


def _role_service(repo: _Repo) -> RoleManagementService:
    store = _build_store(repo)
    return RoleManagementService(
        roles_handler=store.roles_handler,
        permissions_handler=store.permissions_handler,
    )


def _permission_service(repo: _Repo) -> PermissionManagementService:
    store = _build_store(repo)
    return PermissionManagementService(permissions_handler=store.permissions_handler)


def test_admin_user_list_payload_contains_pagination(monkeypatch):
    _patch_admin_stores(monkeypatch, _Repo())
    service = _user_service(_Repo())
    payload = service.list_users_payload(q="aa", page=2, per_page=5)
    assert payload["pagination"]["page"] == 2


def test_create_user_sanitizes_username_and_defaults_user_role(monkeypatch):
    repo = _Repo()
    store = _build_store(repo)
    store.roles_handler.get_all_role_names = lambda: ["user", "admin"]
    service = UserManagementService(
        user_handler=store.user_handler,
        roles_handler=store.roles_handler,
        permissions_handler=store.permissions_handler,
        assay_panel_handler=store.assay_panel_handler,
        common_util=shared_util.common,
    )
    monkeypatch.setattr(user_module, "issue_password_token_for_user", lambda **_: {})
    payload = service.create_context_payload(actor_username="actor")
    assert payload["form"]["fields"]["roles"]["default"] == ["user"]

    service.create_user(
        payload={
            "form_data": {
                "firstname": "Åsa",
                "lastname": "Öberg",
                "fullname": "Åsa Öberg",
                "username": "Åsa Öberg",
                "email": "asa@example.com",
                "job_title": "Scientist",
                "auth_type": "coyote3",
                "password": "StrongPass!123",
                "roles": ["user"],
            }
        },
        actor_username="actor",
    )
    assert repo.created_user["username"] == "asa.oberg"


def test_update_user_keeps_existing_username(monkeypatch):
    repo = _Repo()
    service = _user_service(repo)
    monkeypatch.setattr(user_module, "notify_user_change", lambda **_: {})
    payload = service.update_user(
        user_id="tester",
        payload={
            "form_data": {
                "firstname": "Test",
                "lastname": "User",
                "fullname": "Test User",
                "username": "renamed-user",
                "email": "tester@example.com",
                "job_title": "Analyst",
                "auth_type": "coyote3",
                "roles": ["admin"],
                "permissions": [],
                "deny_permissions": [],
                "assay_groups": [],
                "assays": [],
                "is_active": "true",
            }
        },
        actor_username="actor",
    )
    assert payload["resource_id"] == "tester"
    assert repo.updated_user[1]["username"] == "tester"


def test_admin_role_list_payload_contains_pagination(monkeypatch):
    _patch_admin_stores(monkeypatch, _Repo())
    service = _role_service(_Repo())
    payload = service.list_roles_payload(q="bb", page=3, per_page=7)
    assert payload["pagination"]["per_page"] == 7


def test_permission_list_payload_contains_pagination(monkeypatch):
    _patch_admin_stores(monkeypatch, _Repo())
    service = _permission_service(_Repo())
    payload = service.list_permissions_payload(q="perm", page=2, per_page=10)
    assert payload["pagination"]["q"] == "perm"
    assert "General" in payload["grouped_permissions"]


def test_admin_user_update_preserves_password_when_blank(monkeypatch):
    repo = _Repo()
    _patch_admin_stores(monkeypatch, repo)
    service = _user_service(repo)
    monkeypatch.setattr(user_module, "current_actor", lambda u: u)
    monkeypatch.setattr(user_module, "utc_now", lambda: datetime.now(timezone.utc))
    monkeypatch.setattr(
        user_module, "inject_version_history", lambda **kwargs: kwargs["new_config"]
    )
    monkeypatch.setattr(
        user_module,
        "normalize_managed_form_payload",
        lambda _spec, _form: {
            "username": "TESTER",
            "email": "TESTER@EXAMPLE.COM",
            "firstname": "Test",
            "lastname": "User",
            "fullname": "Test User",
            "job_title": "Analyst",
            "auth_type": "coyote3",
            "password": "",
            "roles": ["admin"],
            "permissions": [],
            "deny_permissions": [],
        },
    )

    payload = service.update_user(
        user_id="tester", payload={"form_data": {}}, actor_username="actor@example.com"
    )

    assert payload["action"] == "update"
    assert repo.updated_user[1]["password"] == "hashed"
    assert repo.updated_user[1]["username"] == "tester"
    assert repo.updated_user[1]["email"] == "tester@example.com"


def test_admin_user_update_raises_when_user_missing(monkeypatch):
    _patch_admin_stores(monkeypatch, _Repo())
    service = _user_service(_Repo())
    with pytest.raises(HTTPException) as exc:
        service.update_user(user_id="missing", payload={"form_data": {}}, actor_username="actor")
    assert exc.value.status_code == 404


def test_admin_user_context_uses_backend_contract_form(monkeypatch):
    repo = _Repo()
    _patch_admin_stores(monkeypatch, repo)
    service = _user_service(repo)
    payload = service.context_payload(user_id="u1")
    assert payload["form"]["form_type"] == "user"


def test_admin_role_update_success(monkeypatch):
    repo = _Repo()
    _patch_admin_stores(monkeypatch, repo)
    service = _role_service(repo)
    monkeypatch.setattr(role_module, "current_actor", lambda u: u)
    monkeypatch.setattr(role_module, "utc_now", lambda: datetime.now(timezone.utc))
    monkeypatch.setattr(
        role_module, "inject_version_history", lambda **kwargs: kwargs["new_config"]
    )
    monkeypatch.setattr(
        role_module,
        "normalize_managed_form_payload",
        lambda _spec, _form: {
            "name": "Admin",
            "label": "Admin",
            "color": "#1f2937",
            "permissions": [],
        },
    )

    payload = service.update_role(
        role_id="admin", payload={"form_data": {}}, actor_username="actor"
    )

    assert payload["action"] == "update"
    assert repo.updated_role[1]["role_id"] == "admin"
    assert repo.updated_role[1]["level"] == 99999


def test_admin_role_update_works_without_db_schema_dependency(monkeypatch):
    repo = _Repo()
    _patch_admin_stores(monkeypatch, repo)
    service = _role_service(_Repo())
    monkeypatch.setattr(role_module, "current_actor", lambda u: u)
    monkeypatch.setattr(role_module, "utc_now", lambda: datetime.now(timezone.utc))
    monkeypatch.setattr(
        role_module, "inject_version_history", lambda **kwargs: kwargs["new_config"]
    )
    monkeypatch.setattr(
        role_module,
        "normalize_managed_form_payload",
        lambda _spec, _form: {
            "name": "Admin",
            "label": "Admin",
            "color": "#1f2937",
            "permissions": [],
        },
    )
    payload = service.update_role(
        role_id="admin", payload={"form_data": {}}, actor_username="actor"
    )
    assert payload["action"] == "update"


def test_permission_create_and_update_success(monkeypatch):
    repo = _Repo()
    _patch_admin_stores(monkeypatch, repo)
    service = _permission_service(repo)
    monkeypatch.setattr(perm_module, "current_actor", lambda u: u)
    monkeypatch.setattr(perm_module, "utc_now", lambda: datetime.now(timezone.utc))
    monkeypatch.setattr(
        perm_module, "inject_version_history", lambda **kwargs: kwargs["new_config"]
    )
    monkeypatch.setattr(
        perm_module,
        "normalize_managed_form_payload",
        lambda _spec, form_data: {
            "permission_name": form_data["permission_name"],
            "label": form_data["permission_name"],
            "category": "General",
            "tags": [],
        },
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


def test_permission_context_and_delete_paths(monkeypatch):
    _patch_admin_stores(monkeypatch, _Repo())
    service = _permission_service(_Repo())
    payload = service.context_payload(permission_id="perm.read")
    deleted = service.delete_permission(permission_id="perm.read")
    assert payload["permission"]["permission_id"] == "perm.read"
    assert deleted["action"] == "delete"


def test_username_and_email_exists(monkeypatch):
    _patch_admin_stores(monkeypatch, _Repo())
    service = _user_service(_Repo())
    assert service.username_exists(username="exists")
    assert not service.email_exists(email="new@example.com")
