"""Installed identities remain immutable even to authenticated superusers."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from api.application.accounts.roles import RoleManagementService
from api.application.accounts.users import UserManagementService
from api.application.ingest.collection_writes import upsert_collection_document
from api.domain.core.exceptions import AppError
from api.interfaces.http.admin import users as routes


@pytest.mark.parametrize("operation", ["update", "toggle", "delete"])
def test_installed_role_rejects_all_admin_writes(operation):
    repo = Mock()
    repo.get_role.return_value = {"role_id": "installed", "system_managed": True}
    service = RoleManagementService(roles_repository=repo, permissions_repository=Mock())
    kwargs = {"role_id": "installed"}
    if operation == "update":
        kwargs.update(payload={"form_data": {"system_managed": False}}, actor_username="operator")
    with pytest.raises(AppError):
        getattr(service, operation + "_role")(**kwargs)
    repo.update_role.assert_not_called()
    repo.toggle_role_active.assert_not_called()
    repo.delete_role.assert_not_called()


@pytest.mark.parametrize("operation", ["update", "toggle", "delete", "profile"])
def test_installed_user_rejects_admin_and_profile_writes(operation):
    repo = Mock()
    repo.user_with_id.return_value = {
        "username": "bootstrap",
        "system_managed": True,
        "roles": ["superuser"],
    }
    service = UserManagementService(
        user_repository=repo,
        roles_repository=Mock(),
        permissions_repository=Mock(),
        assay_panel_repository=Mock(),
        common_util=Mock(),
    )
    kwargs = {"user_id": "bootstrap", "actor_is_superuser": True}
    if operation == "profile":
        with pytest.raises(AppError):
            service.update_own_profile(username="bootstrap", payload={"fullname": "Changed"})
        return
    if operation == "update":
        kwargs.update(payload={"form_data": {"system_managed": False}}, actor_username="operator")
    with pytest.raises(AppError):
        getattr(service, operation + "_user")(**kwargs)
    repo.update_user.assert_not_called()
    repo.toggle_user_active.assert_not_called()
    repo.delete_user.assert_not_called()


@pytest.mark.parametrize(
    ("field", "permission"),
    [
        ("roles", "user:role:edit"),
        ("asp_ids", "user:group:edit"),
        ("asp_groups", "user:group:edit"),
        ("environments", "user:group:edit"),
    ],
)
def test_assignment_fields_require_specific_permission_even_when_empty(
    monkeypatch, field, permission
):
    checked = []

    def check(user, *, permission):
        checked.append(permission)
        raise HTTPException(403)

    monkeypatch.setattr(routes, "_enforce_access", check)
    with pytest.raises(HTTPException) as failure:
        routes._enforce_assignment_permissions(SimpleNamespace(), {"form_data": {field: []}})
    assert failure.value.status_code == 403
    assert checked == [permission]


def test_profile_only_edit_does_not_require_assignment_permissions(monkeypatch):
    check = Mock()
    monkeypatch.setattr(routes, "_enforce_access", check)
    routes._enforce_assignment_permissions(SimpleNamespace(), {"form_data": {"fullname": "Reader"}})
    check.assert_not_called()


@pytest.mark.parametrize("collection", ["users", "roles", "permissions"])
def test_ingest_cannot_replace_installed_identity(collection):
    repository = Mock()
    repository.find_one.return_value = {"system_managed": True}
    service = SimpleNamespace(_collection=Mock(return_value=repository))
    with pytest.raises(AppError):
        upsert_collection_document(
            service,
            collection=collection,
            match={"_id": "installed"},
            document={"system_managed": False},
        )
    repository.replace_one.assert_not_called()
