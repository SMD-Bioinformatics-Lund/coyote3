"""Integration-style admin route tests using shared fake-store harness."""

from __future__ import annotations

from api.routers import roles
from tests.fixtures.api import mock_collections as fx


def test_list_roles_read_with_fake_store(monkeypatch):
    """Handle test list roles read with fake store.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(roles.util.common, "convert_to_serializable", lambda payload: payload)
    service = type(
        "_Service",
        (),
        {"list_roles_payload": staticmethod(lambda **_: {"roles": [fx.role_doc()]})},
    )()

    payload = roles.list_roles_read(user=fx.api_user(), service=service)

    assert payload["roles"][0]["_id"] == fx.role_doc()["_id"]
    assert payload["roles"][0]["level"] == int(fx.role_doc().get("level") or 0)


def test_create_role_context_read_with_fake_store(monkeypatch):
    """Handle test create role context read with fake store.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr(roles.util.common, "utc_now", lambda: "NOW")
    monkeypatch.setattr(roles.util.common, "convert_to_serializable", lambda payload: payload)
    service = type(
        "_Service",
        (),
        {
            "create_context_payload": staticmethod(
                lambda **kwargs: {
                    "selected_schema": fx.schema_doc(),
                    "schema": {
                        "fields": {
                            "created_by": {"default": "tester"},
                        }
                    },
                }
            )
        },
    )()

    expected_schema_id = fx.schema_doc()["_id"]
    payload = roles.create_role_context_read(
        schema_id=expected_schema_id,
        user=fx.api_user(),
        service=service,
    )

    assert payload["selected_schema"]["_id"] == expected_schema_id
    assert payload["schema"]["fields"]["created_by"]["default"] == "tester"
