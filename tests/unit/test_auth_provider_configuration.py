"""Tests for deployment-scoped authentication-provider configuration."""

from __future__ import annotations

import pytest

from coyote3.config.constants import _auth_provider_options


def test_authentication_provider_override_narrows_center_configuration():
    """A deployment can expose only local auth while LDAP remains center-supported."""
    assert _auth_provider_options(("local", "ldap"), "local") == ("local",)


def test_authentication_provider_override_replaces_center_default():
    """A deployment can enable LDAP even when the center default is local-only."""
    assert _auth_provider_options(("local",), "local,ldap") == ("local", "ldap")


def test_authentication_provider_override_cannot_add_unsupported_provider():
    """A deployment override cannot introduce an unimplemented provider."""
    with pytest.raises(RuntimeError, match="unsupported provider"):
        _auth_provider_options(("local", "ldap"), "local,oidc")
