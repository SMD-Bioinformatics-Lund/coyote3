"""Credential inspection uses a bounded read command and always closes its owned client."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from coyote_mongo import security_scope


@pytest.mark.parametrize("fails", [False, True])
def test_privilege_probe_closes_owned_client_and_uses_only_connection_status(monkeypatch, fails):
    context = MagicMock()
    admin = MagicMock()
    context.__enter__.return_value = SimpleNamespace(admin=admin)
    admin.command.return_value = {
        "authInfo": {"authenticatedUserPrivileges": [{"resource": {"db": "demo"}}]}
    }
    if fails:
        admin.command.side_effect = RuntimeError("synthetic failure")
    factory = MagicMock(return_value=context)
    monkeypatch.setattr(security_scope, "MongoClient", factory)
    if fails:
        with pytest.raises(RuntimeError, match="synthetic failure"):
            security_scope.authenticated_privileges("mongodb://synthetic")
    else:
        assert security_scope.authenticated_privileges("mongodb://synthetic") == [
            {"resource": {"db": "demo"}}
        ]
    factory.assert_called_once_with(
        "mongodb://synthetic", serverSelectionTimeoutMS=5000, connectTimeoutMS=5000
    )
    admin.command.assert_called_once_with("connectionStatus", showPrivileges=True)
    context.__exit__.assert_called_once()
