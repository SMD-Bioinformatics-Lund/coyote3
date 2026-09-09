"""Tests for optional LDAP runtime configuration."""

from __future__ import annotations

import json
import os
import ssl
import subprocess
import sys
from unittest.mock import Mock

import pytest
from ldap3 import AUTO_BIND_NO_TLS, AUTO_BIND_TLS_BEFORE_BIND, MOCK_SYNC, Connection, Server
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError

from api.infra.integrations.ldap import LdapManager


def test_ldap_manager_stays_disabled_without_host():
    """A local-only deployment must not fail while initializing LDAP."""
    manager = LdapManager()

    assert manager.init_from_config({"LDAP_HOST": ""}) is False
    assert manager.is_configured is False


@pytest.mark.parametrize(
    "host,options,port,encrypted,mode",
    [
        ("ldap.example.test", {}, 389, False, AUTO_BIND_TLS_BEFORE_BIND),
        ("ldap://ldap.example.test", {"LDAP_USE_TLS": True}, 389, False, AUTO_BIND_TLS_BEFORE_BIND),
        ("ldaps://ldap.example.test", {"LDAP_USE_TLS": True}, 636, True, AUTO_BIND_NO_TLS),
        ("ldap.example.test", {"LDAP_USE_SSL": True}, 636, True, AUTO_BIND_NO_TLS),
        ("ldaps://ldap.example.test:1636", {}, 1636, True, AUTO_BIND_NO_TLS),
        ("ldap://[::1]:1389", {}, 1389, False, AUTO_BIND_TLS_BEFORE_BIND),
        ("ldaps://ldap.example.test:1636", {"LDAP_PORT": 2636}, 2636, True, AUTO_BIND_NO_TLS),
        ("ldap.example.test", {"LDAP_USE_TLS": False}, 389, False, AUTO_BIND_NO_TLS),
    ],
)
def test_transport_selection_and_certificate_verification(host, options, port, encrypted, mode):
    manager = LdapManager()
    config = {"LDAP_HOST": host, **options}
    original = dict(config)
    assert manager.init_from_config(config)
    assert config == original
    assert manager._server.port == port
    assert manager._server.ssl is encrypted
    assert manager._server.tls.validate == ssl.CERT_REQUIRED
    assert manager._auto_bind_mode() == mode


@pytest.mark.parametrize(
    "options",
    [
        {"LDAP_HOST": "https://ldap.example.test"},
        {"LDAP_HOST": "ldap://user:secret@ldap.example.test"},
        {"LDAP_HOST": "ldap://ldap.example.test/ou=people"},
        {"LDAP_PORT": -1},
        {"LDAP_CONNECT_TIMEOUT": 0},
        {"LDAP_BINDDN": "cn=search,dc=example,dc=test"},
        {"LDAP_SECRET": "synthetic"},
    ],
)
def test_invalid_configuration_is_rejected(options):
    manager = LdapManager()
    with pytest.raises(ValueError):
        manager.init_from_config({"LDAP_HOST": "ldap.example.test", **options})
    assert not manager.is_configured


@pytest.fixture
def manager():
    instance = LdapManager()
    instance.init_from_config({"LDAP_HOST": "ldap.example.test", "LDAP_USE_TLS": True})
    return instance


@pytest.mark.parametrize("password,expected", [("Synthetic!123", True), ("incorrect", False)])
def test_search_then_user_bind_with_synthetic_directory(manager, monkeypatch, password, expected):
    """Exercise real ldap3 filter/search/bind logic against an in-memory directory."""
    dn = "cn=operator,ou=people,dc=example,dc=test"
    connections = []

    def connect(user, password, **kwargs):
        connection = Connection(
            Server("synthetic"), user=user, password=password, client_strategy=MOCK_SYNC
        )
        connection.strategy.add_entry(
            dn,
            {
                "objectClass": ["person", "inetOrgPerson"],
                "cn": "operator",
                "sn": "Operator",
                "mail": "operator@example.test",
                "userPassword": "Synthetic!123",
            },
        )
        connection.bind()
        connections.append(connection)
        return connection

    monkeypatch.setattr(manager, "_connect", connect)
    assert (
        manager.authenticate(
            "operator@example.test", password, "ou=people,dc=example,dc=test", "mail"
        )
        is expected
    )
    assert len(connections) == 2
    assert all(not connection.bound for connection in connections)


@pytest.mark.parametrize("error", [LDAPBindError, LDAPSocketOpenError])
def test_lookup_connection_failures_are_denied_without_exposing_values(
    manager, monkeypatch, caplog, error
):
    monkeypatch.setattr(manager, "_connect", Mock(side_effect=error("private directory detail")))
    assert not manager.authenticate("operator@example.test", "secret", "dc=example,dc=test", "mail")
    assert "private directory detail" not in caplog.text
    assert "operator@example.test" not in caplog.text


@pytest.mark.parametrize("count", [0, 2])
def test_missing_or_ambiguous_entries_are_denied(manager, monkeypatch, count):
    connection = Mock(
        bound=True, response=[{"type": "searchResEntry", "dn": "cn=operator"}] * count
    )
    connection.search.return_value = True
    monkeypatch.setattr(manager, "_connect", Mock(return_value=connection))
    assert not manager.authenticate("operator@example.test", "secret", "dc=example,dc=test", "mail")
    connection.unbind.assert_called_once()


def test_filter_values_are_escaped_and_search_is_bounded(manager, monkeypatch):
    connection = Mock(bound=True, response=[])
    monkeypatch.setattr(manager, "_connect", Mock(return_value=connection))
    assert manager._lookup_user_dn("*)(mail=*)", "dc=example,dc=test", "mail") is None
    assert connection.search.call_args.args[1] == r"(mail=\2a\29\28mail=\2a\29)"
    assert connection.search.call_args.kwargs["size_limit"] == 2


def test_service_bind_uses_configured_account(manager, monkeypatch):
    manager._config.update(LDAP_BINDDN="cn=search,dc=example,dc=test", LDAP_SECRET="synthetic")
    connection = Mock(bound=True, response=[])
    connect = Mock(return_value=connection)
    monkeypatch.setattr(manager, "_connect", connect)
    manager._lookup_user_dn("operator@example.test", "dc=example,dc=test", "mail")
    assert connect.call_args.kwargs == {
        "user": "cn=search,dc=example,dc=test",
        "password": "synthetic",
        "anonymous": False,
        "read_only": True,
    }


def test_unconfigured_search_never_attempts_a_bind(manager, monkeypatch):
    connect = Mock()
    monkeypatch.setattr(manager, "_connect", connect)
    assert not manager.authenticate("operator@example.test", "secret")
    assert not manager.authenticate("", "secret")
    assert not manager.authenticate("operator@example.test", "")
    connect.assert_not_called()


@pytest.mark.parametrize(
    "ssl_flag,tls_flag,expected", [("true", "false", [True, False]), ("0", "1", [False, True])]
)
def test_transport_flags_are_loaded_from_environment(ssl_flag, tls_flag, expected):
    code = (
        "import json; from api.config.runtime_settings import DirectoryAndReportSettings as S; "
        "print(json.dumps([S.LDAP_USE_SSL, S.LDAP_USE_TLS, S.LDAP_PORT, S.LDAP_CONNECT_TIMEOUT]))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
        env={
            **os.environ,
            "LDAP_USE_SSL": ssl_flag,
            "LDAP_USE_TLS": tls_flag,
            "LDAP_PORT": "1636",
            "LDAP_CONNECT_TIMEOUT": "7",
        },
    )
    assert json.loads(result.stdout) == [*expected, 1636, 7]


@pytest.mark.parametrize("verify", [True, False])
@pytest.mark.parametrize("host", ["ldap://ldap.example.test", "ldaps://ldap.example.test"])
def test_certificate_verification_toggle_preserves_transport(verify, host):
    manager = LdapManager()
    manager.init_from_config({"LDAP_HOST": host, "LDAP_VERIFY_CERT": verify})
    assert manager._server.tls.validate == (ssl.CERT_REQUIRED if verify else ssl.CERT_NONE)
    assert manager._auto_bind_mode() == (
        AUTO_BIND_NO_TLS if host.startswith("ldaps:") else AUTO_BIND_TLS_BEFORE_BIND
    )


@pytest.mark.parametrize(
    "value,expected", [("0", False), ("false", False), ("1", True), ("true", True)]
)
def test_certificate_verification_flag_is_loaded_from_environment(value, expected):
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from api.config.runtime_settings import DirectoryAndReportSettings as S; print(S.LDAP_VERIFY_CERT)",
        ],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "LDAP_VERIFY_CERT": value},
    )
    assert result.stdout.strip() == str(expected)


def test_connection_disables_referrals_and_bounds_receive_time(manager, monkeypatch):
    factory = Mock()
    monkeypatch.setattr("api.infra.integrations.ldap.Connection", factory)
    manager._connect("cn=operator", "synthetic")
    assert factory.call_args.kwargs["auto_bind"] == AUTO_BIND_TLS_BEFORE_BIND
    assert factory.call_args.kwargs["auto_referrals"] is False
    assert factory.call_args.kwargs["receive_timeout"] == 10
    assert factory.call_args.kwargs["read_only"] is True


def test_user_bind_failure_after_successful_lookup_is_denied(manager, monkeypatch):
    monkeypatch.setattr(
        manager, "_lookup_user_dn", Mock(return_value="cn=operator,dc=example,dc=test")
    )
    monkeypatch.setattr(manager, "_connect", Mock(side_effect=LDAPBindError("synthetic")))
    assert not manager.authenticate("operator@example.test", "wrong", "dc=example,dc=test", "mail")


def test_cleanup_failure_does_not_turn_a_denied_login_into_an_exception(manager, monkeypatch):
    connection = Mock(bound=True, response=[])
    connection.unbind.side_effect = LDAPSocketOpenError("synthetic")
    monkeypatch.setattr(manager, "_connect", Mock(return_value=connection))
    assert not manager.authenticate("operator@example.test", "wrong", "dc=example,dc=test", "mail")
