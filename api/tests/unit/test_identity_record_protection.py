"""Installed identities remain immutable even to authenticated superusers."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from api_test_support import application_sdk as sdk_fixtures
from api_test_support import mock_collections as fx
from coyote.application.operations import Users
from coyote.domain.exceptions import AppError


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
