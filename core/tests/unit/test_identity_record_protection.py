"""Installed identities remain immutable even to authenticated superusers."""

from unittest.mock import Mock

import pytest
from coyote.application.accounts.roles import RoleManagementService
from coyote.application.accounts.users import UserManagementService
from coyote.domain.exceptions import AppError


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
        password_token_issuer=lambda **_: {},
        user_change_notifier=lambda **_: {},
        user_repository=repo,
        roles_repository=Mock(),
        permissions_repository=Mock(),
        assay_panel_repository=Mock(),
        password_hasher=Mock(),
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
