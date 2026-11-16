"""Demo host installation rejects unsafe handles and retains connection ownership."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from coyote_demo import host
from coyote_mongo import connections, security_scope
from demo_test_support.deployment import demo_privileges, demo_settings


def _databases(client=None):
    """Return named synthetic handles sharing one explicitly owned client."""
    client = client or object()
    return {
        key: SimpleNamespace(name=name, client=client)
        for key, name in zip(
            ("primary", "identity", "knowledgebase", "bam"),
            host.DEMO_DATABASES.values(),
            strict=True,
        )
    }


def test_host_validates_each_actual_client_once(monkeypatch):
    probe = Mock(return_value=demo_privileges())
    monkeypatch.setattr(security_scope, "authenticated_client_privileges", probe)
    databases = _databases()
    host.validate_database_clients(demo_settings(), **databases)
    probe.assert_called_once_with(databases["primary"].client)


def test_host_rejects_ordinary_handles_before_privilege_probe(monkeypatch):
    probe = Mock()
    monkeypatch.setattr(security_scope, "authenticated_client_privileges", probe)
    with pytest.raises(ValueError, match="dedicated database handles"):
        host.validate_database_clients(
            demo_settings(), primary=SimpleNamespace(name="ordinary", client=object())
        )
    probe.assert_not_called()


def test_host_rejects_broad_database_credentials(monkeypatch):
    monkeypatch.setattr(
        security_scope,
        "authenticated_client_privileges",
        lambda client: [{"resource": {"anyResource": True}, "actions": ["anyAction"]}],
    )
    with pytest.raises(ValueError, match="restricted"):
        host.validate_database_clients(demo_settings(), **_databases())


@pytest.mark.parametrize(
    "starter,apply", [(False, False), (False, True), (True, False), (True, True)]
)
def test_host_plans_without_writes_and_closes_connections(monkeypatch, starter, apply):
    owned = SimpleNamespace(databases=_databases(), close=Mock())
    monkeypatch.setattr(connections, "MongoConnections", lambda settings: owned)
    monkeypatch.setattr(
        security_scope, "authenticated_client_privileges", lambda client: demo_privileges()
    )
    installer = Mock()
    installer.configuration.return_value = {"samples": [{"name": "synthetic"}]}
    installer.plan.return_value.model_dump.return_value = {"configuration_installed": False}
    installer.install_starter.return_value = {"status": "installed"}
    installer.install_configuration.return_value = {"status": "installed"}
    monkeypatch.setattr(host, "build_demo_service", lambda *args, **kwargs: installer)
    result = host.install_resources(
        demo_settings(), actor="demo.admin", starter=starter, apply=apply
    )
    owned.close.assert_called_once()
    if apply:
        method = installer.install_starter if starter else installer.install_configuration
        method.assert_called_once_with("demo.admin")
        assert result == {"status": "installed"}
    else:
        installer.install_starter.assert_not_called()
        installer.install_configuration.assert_not_called()
        assert result == ({"configuration_installed": False} if starter else {"samples": 1})


def test_host_closes_connections_when_preflight_fails(monkeypatch):
    owned = SimpleNamespace(databases=_databases(), close=Mock())
    monkeypatch.setattr(connections, "MongoConnections", lambda settings: owned)
    monkeypatch.setattr(security_scope, "authenticated_client_privileges", lambda client: [])
    with pytest.raises(ValueError):
        host.install_resources(demo_settings(), actor="demo.admin", starter=True, apply=True)
    owned.close.assert_called_once()
