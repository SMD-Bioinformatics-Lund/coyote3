"""Tests for optional LDAP runtime configuration."""

from __future__ import annotations

from api.infra.integrations.ldap import LdapManager


def test_ldap_manager_stays_disabled_without_host():
    """A local-only deployment must not fail while initializing LDAP."""
    manager = LdapManager()

    assert manager.init_from_config({"LDAP_HOST": ""}) is False
    assert manager.is_configured is False
