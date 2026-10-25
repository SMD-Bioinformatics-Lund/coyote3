"""Installed identities remain immutable even to authenticated superusers."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from api.infra.mongo.repositories.ingest_gateway import IngestCollectionGateway
from coyote3.application.accounts.roles import RoleManagementService
from coyote3.application.accounts.users import UserManagementService
from coyote3.application.ingest.collection_writes import upsert_collection_document
from coyote3.application.operations import Users
from coyote3.domain.exceptions import AppError
from tests.fixtures.api import application_sdk as sdk_fixtures
from tests.fixtures.api import mock_collections as fx


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
    user = fx.api_user()
    user.roles = ["account-editor"]
    service = Mock()
    operations = sdk_fixtures.authorized_operations(Users, service, user)

    def allowed(actor, required, **kwargs):
        checked.append(required)
        return required != permission

    operations._runtime.policy_factory = lambda actor: SimpleNamespace(permission_allowed=allowed)
    with pytest.raises(AppError) as failure:
        operations.update_user(user_id="synthetic", payload={"form_data": {field: []}})
    assert failure.value.status_code == 403
    assert checked == ["user:edit", permission]
    assert not service.method_calls


def test_profile_only_edit_does_not_require_assignment_permissions(monkeypatch):
    checked = []
    user = fx.api_user()
    user.roles = ["account-editor"]
    service = Mock()
    service.update_user.return_value = {"status": "ok"}
    operations = sdk_fixtures.authorized_operations(Users, service, user)
    operations._runtime.policy_factory = lambda actor: SimpleNamespace(
        permission_allowed=lambda actor, permission, **kwargs: checked.append(permission) or True
    )
    operations.update_user(user_id="synthetic", payload={"form_data": {"fullname": "Reader"}})
    assert checked == ["user:edit"]


@pytest.mark.parametrize("collection", ["users", "roles", "permissions"])
def test_ingest_cannot_replace_installed_identity(collection):
    repository = Mock()
    repository.find_one.return_value = {"system_managed": True}
    service = SimpleNamespace(
        collection_gateway=IngestCollectionGateway(collections={collection: repository})
    )
    with pytest.raises(AppError):
        upsert_collection_document(
            service,
            collection=collection,
            match={"_id": "installed"},
            document={"system_managed": False},
        )
    repository.replace_one.assert_not_called()
