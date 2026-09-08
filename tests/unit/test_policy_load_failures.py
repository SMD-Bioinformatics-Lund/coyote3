"""Authorization infrastructure failures remain observable and fail closed."""

import logging
from types import SimpleNamespace

from api.security.policy import _active_permission_ids, _role_docs_by_id


def test_repository_failures_are_logged_without_private_error_content(caplog):
    def fail(**kwargs):
        raise RuntimeError("private database details")

    with caplog.at_level(logging.ERROR):
        assert _active_permission_ids(SimpleNamespace(get_all_permissions=fail)) == set()
        assert _role_docs_by_id(SimpleNamespace(get_all_roles=fail)) == {}
    assert "authorization_permissions_load_failed" in caplog.text
    assert "authorization_roles_load_failed" in caplog.text
    assert "private database details" not in caplog.text
