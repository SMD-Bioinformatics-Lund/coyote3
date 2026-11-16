"""Demonstration operations authenticate and authorize before resolving write services."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote.application.operations.runtime import ApplicationRuntime
from coyote.domain.exceptions import AppError
from coyote_demo.operations import DemoInstallation


@pytest.mark.parametrize("method", ["plan", "starter", "configuration", "sample"])
@pytest.mark.parametrize("allowed", [False, True])
def test_operations_keep_current_permissions_and_actor(method, allowed):
    actor = SimpleNamespace(username="demo.admin", is_superuser=False, must_change_password=False)
    audit, service, factory = Mock(), Mock(), Mock()
    factory.return_value = service
    runtime = ApplicationRuntime(
        authenticate=lambda: actor,
        policy_factory=lambda user: SimpleNamespace(
            permission_allowed=lambda user, permission, **_: (
                allowed and permission == "demo:install"
            )
        ),
        sample_loader=Mock(),
        assay_loader=Mock(),
        audit_access=audit,
    )
    operation = getattr(DemoInstallation(runtime, factory), method)
    service_method = {
        "plan": "plan",
        "starter": "install_starter",
        "configuration": "install_configuration",
        "sample": "install_sample",
    }[method]
    getattr(service, service_method).return_value = {"status": "synthetic"}
    args = ("first_sample",) if method == "sample" else ()
    if not allowed:
        with pytest.raises(AppError) as error:
            operation(*args)
        assert error.value.status_code == 403
        factory.assert_not_called()
        assert not audit.call_args.args[0].allowed
        return
    assert operation(*args) == {"status": "synthetic"}
    expected = () if method == "plan" else (*args, actor.username)
    getattr(service, service_method).assert_called_once_with(*expected)
    assert audit.call_args.args[0].allowed
    assert audit.call_args.args[0].operation == f"installation.{method}"
