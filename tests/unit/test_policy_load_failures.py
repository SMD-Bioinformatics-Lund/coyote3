"""Authorization infrastructure failures remain observable and fail closed."""

import logging
from types import SimpleNamespace

from api.security.policy import AccessPolicy, _active_permission_ids, _role_docs_by_id


def test_repository_failures_are_logged_without_private_error_content(caplog):
    def fail(**kwargs):
        raise RuntimeError("private database details")

    with caplog.at_level(logging.ERROR):
        assert _active_permission_ids(SimpleNamespace(get_all_permissions=fail)) == set()
        assert _role_docs_by_id(SimpleNamespace(get_all_roles=fail)) == {}
    assert "authorization_permissions_load_failed" in caplog.text
    assert "authorization_roles_load_failed" in caplog.text
    assert "private database details" not in caplog.text


def test_empty_permission_catalog_denies_even_an_enforcer_grant():
    """Missing catalog data cannot turn a wildcard grant into authorization."""
    policy = AccessPolicy(
        enforcer=SimpleNamespace(enforce=lambda *args: True),
        active_permissions=set(),
        principal_scope=None,
    )
    assert not policy.permission_known("sample:view")
    assert not policy.permission_allowed(SimpleNamespace(username="operator"), "sample:view")
    policy.active_permissions.add("sample:view")
    assert policy.permission_allowed(SimpleNamespace(username="operator"), "sample:view")
