"""Access-control matrix tests for role-permission and scope behavior."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.security.access import ApiUser, _enforce_access, _get_sample_for_api, is_public_api_path


@pytest.fixture(autouse=True)
def _isolate_policy_repositories(monkeypatch: pytest.MonkeyPatch):
    """Keep access-control unit tests independent from runtime repositories."""
    monkeypatch.setattr("api.security.access.get_permissions_repository", lambda: None)
    monkeypatch.setattr(
        "api.security.access.get_roles_repository",
        lambda: type(
            "_Roles",
            (),
            {
                "get_all_roles": staticmethod(
                    lambda: [
                        {
                            "role_id": "user",
                            "is_active": True,
                            "permissions": ["report:preview", "sample:view:own"],
                        },
                        {
                            "role_id": "manager",
                            "is_active": True,
                            "permissions": ["report:create"],
                        },
                    ]
                )
            },
        )(),
    )


def _u(
    *,
    role: str = "user",
    level: int = 1,
    permissions: list[str] | None = None,
) -> ApiUser:
    """U.

    Args:
            role: Role. Keyword-only argument.
            level: Level. Keyword-only argument.
            permissions: Permissions. Keyword-only argument.
    Returns:
            The  u result.
    """
    return ApiUser(
        id="u",
        email="u@example.com",
        fullname="U",
        username="user",
        roles=[role],
        role=role,
        access_level=level,
        permissions=permissions or [],
        asp_ids=[],
        asp_groups=[],
        envs=[],
        asp_map={},
        auth_type=["local"],
    )


def test_enforce_access_allows_matching_permission():
    """Test enforce access allows matching permission.

    Returns:
        The function result.
    """
    _enforce_access(_u(permissions=["report:preview"]), permission="report:preview")


def test_login_provider_discovery_is_a_public_bootstrap_endpoint():
    """The login page must discover enabled providers before a session exists."""
    assert is_public_api_path("/api/v1/auth/providers") is True


def test_enforce_access_allows_permission_inside_resource_scope():
    """Permission grants should be constrained by assigned resource attributes."""
    user = _u(permissions=["sample:view:own"])
    user.asp_ids = ["hema_gmsv1"]
    user.envs = ["production"]
    user.asp_groups = ["hematology"]

    _enforce_access(
        user,
        permission="sample:view:own",
        context={
            "asp_id": "HEMA_GMSV1",
            "environment": "production",
            "asp_group": "hematology",
        },
    )


def test_enforce_access_does_not_expand_environment_aliases():
    """Access scopes use the stored environment vocabulary verbatim."""
    user = _u(permissions=["sample:view:own"])
    user.asp_ids = ["hema_gmsv1"]
    user.envs = ["production"]
    user.asp_groups = ["hematology"]

    with pytest.raises(HTTPException) as exc:
        _enforce_access(
            user,
            permission="sample:view:own",
            context={
                "asp_id": "HEMA_GMSV1",
                "environment": "prod",
                "asp_group": "hematology",
            },
        )

    assert exc.value.status_code == 403


def test_enforce_access_denies_permission_outside_resource_scope():
    """Permission grants should not bypass assay, profile, or assay-group scope."""
    user = _u(permissions=["sample:view:own"])
    user.asp_ids = ["hema_gmsv1"]
    user.envs = ["production"]
    user.asp_groups = ["hematology"]

    with pytest.raises(HTTPException) as exc:
        _enforce_access(
            user,
            permission="sample:view:own",
            context={
                "asp_id": "solid_panel",
                "environment": "production",
                "asp_group": "solid",
            },
        )

    assert exc.value.status_code == 403


def test_enforce_access_allows_permission_from_role_policy():
    """Role documents, not route min-level gates, grant protected actions."""
    _enforce_access(_u(role="manager", level=1), permission="report:create")


def test_enforce_access_denies_when_role_lacks_permission():
    """A high access level alone must not grant a permission absent from role policy."""
    with pytest.raises(HTTPException) as exc:
        _enforce_access(_u(level=99999, permissions=[]), permission="report:create")
    assert exc.value.status_code == 403


def test_enforce_access_superuser_bypasses_all_checks():
    """Superuser should bypass permission and scope checks."""
    _enforce_access(
        _u(role="superuser", level=0, permissions=[]),
        permission="permission.policy:delete",
    )


def test_get_sample_for_api_returns_specific_scope_error(monkeypatch):
    """Sample lookup should explain assay-scope denials clearly."""
    user = _u(role="user", level=9, permissions=["sample:view:own"])
    user.asp_ids = ["wgs"]
    sample = {"_id": "s1", "name": "S1", "asp_id": "hema_gmsv1"}

    monkeypatch.setattr(
        "api.security.access.get_sample_repository",
        lambda: type(
            "_Handler",
            (),
            {
                "get_sample": staticmethod(lambda sample_id: sample),
                "get_sample_by_id": staticmethod(lambda sample_id: None),
            },
        )(),
    )

    with pytest.raises(HTTPException) as exc:
        _get_sample_for_api("S1", user)

    assert exc.value.status_code == 403
    assert exc.value.detail["error"] == "Sample 'S1' is outside your assay scope"
    assert exc.value.detail["category"] == "scope"
