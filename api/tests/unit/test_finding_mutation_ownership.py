"""Finding mutations reject cross-sample identifiers before changing data."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from api_test_support import application_sdk as sdk_fixtures
from api_test_support import mock_collections as fx
from api_test_support.permission_catalog import PermissionCatalog
from coyote.application.operations import FlagChange
from coyote.domain.common.errors import AppError
from coyote_api.interfaces.http.v1.clinical.dna import small_variants as annotation_routes
from coyote_api.security import access


@pytest.mark.parametrize("scope", ["local", "global"])
@pytest.mark.parametrize("global_allowed", [False, True])
def test_annotation_route_requires_the_extra_global_permission(monkeypatch, scope, global_allowed):
    """An own-comment grant alone cannot authorize a shared annotation write."""
    permissions = ["variant.comment:add:own"]
    if global_allowed:
        permissions.append("variant.comment:add:global")
    roles = SimpleNamespace(
        get_all_roles=lambda: [{"role_id": "commenter", "permissions": permissions}]
    )
    monkeypatch.setattr(access, "get_roles_repository", lambda: roles)
    monkeypatch.setattr(access, "get_permissions_repository", PermissionCatalog)
    principal = SimpleNamespace(
        username="reviewer",
        roles=["commenter"],
        is_superuser=False,
        asp_ids=["*"],
        assay_access=[{"asp_id": "synthetic", "environments": ["testing"]}],
        asp_groups=["*"],
        envs=["testing"],
    )
    sample = {"_id": "sample", "asp_id": "synthetic", "environment": "testing"}
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda *_args: sample)
    service = Mock()
    service.create_annotation.return_value = "variant_comment"
    operations = sdk_fixtures.sample_operations(service, principal, "sample")
    operations._runtime.policy_factory = lambda actor: access.build_access_policy(
        user=actor, roles_repository=roles, permissions_repository=PermissionCatalog()
    )
    arguments = {
        "payload": {"id": "finding", "form_data": {"global": scope, "text": "note"}},
        "user": principal,
        "service": operations,
    }
    if scope == "global" and not global_allowed:
        with pytest.raises(AppError) as failure:
            annotation_routes.add_variant_comment_change("sample", **arguments)
        assert failure.value.status_code == 403
        service.create_annotation.assert_not_called()
    else:
        annotation_routes.add_variant_comment_change("sample", **arguments)
        assert service.create_annotation.call_args.kwargs["sample"] == sample


def test_sample_authorization_precedes_finding_validation(monkeypatch):
    """Denied sample scope prevents both finding validation and mutation in the SDK."""
    service = Mock()
    monkeypatch.setattr(sdk_fixtures, "load_sample", lambda *_: {"_id": "sample"})
    user = fx.api_user()
    user.roles = ["curator"]
    operations = sdk_fixtures.finding_operations(service, "cnv", user, "sample")
    operations._runtime.policy_factory = lambda actor: SimpleNamespace(
        permission_allowed=lambda *args, **kwargs: True,
        scope_allowed=lambda *args, **kwargs: False,
    )
    with pytest.raises(AppError) as failure:
        operations.set_flags(FlagChange(resource_ids=["finding"], flag="interesting", value=True))
    assert failure.value.status_code == 403
    service.require_resource_for_sample.assert_not_called()
    service.set_cnv_flag.assert_not_called()
