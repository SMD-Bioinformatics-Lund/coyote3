"""Tests for deployment-scoped authentication-provider configuration."""

from __future__ import annotations

import pytest

from api.config.constants import _auth_provider_options


def test_authentication_provider_override_narrows_center_configuration(monkeypatch):
    """A deployment can expose only local auth while LDAP remains center-supported."""
    monkeypatch.setenv("AUTHENTICATION_PROVIDERS", "local")

    assert _auth_provider_options(("local", "ldap")) == ("local",)


def test_authentication_provider_override_replaces_center_default(monkeypatch):
    """A deployment can enable LDAP even when the center default is local-only."""
    monkeypatch.setenv("AUTHENTICATION_PROVIDERS", "local,ldap")

    assert _auth_provider_options(("local",)) == ("local", "ldap")


def test_authentication_provider_override_cannot_add_unsupported_provider(monkeypatch):
    """A deployment override cannot introduce an unimplemented provider."""
    monkeypatch.setenv("AUTHENTICATION_PROVIDERS", "local,oidc")

    with pytest.raises(RuntimeError, match="unsupported provider"):
        _auth_provider_options(("local", "ldap"))
