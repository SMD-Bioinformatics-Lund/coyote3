"""Access-control matrix tests for role/level/permission behavior."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.security.access import ApiUser, _enforce_access, _get_sample_for_api


def _u(
    *,
    role: str = "user",
    level: int = 1,
    permissions: list[str] | None = None,
    denied: list[str] | None = None,
) -> ApiUser:
    """U.

    Args:
            role: Role. Keyword-only argument.
            level: Level. Keyword-only argument.
            permissions: Permissions. Keyword-only argument.
            denied: Denied. Keyword-only argument.

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
        denied_permissions=denied or [],
        assays=[],
        assay_groups=[],
        envs=[],
        asp_map={},
    )


def test_enforce_access_allows_matching_permission():
    """Test enforce access allows matching permission.

    Returns:
        The function result.
    """
    _enforce_access(_u(permissions=["report:preview"]), permission="report:preview")


def test_enforce_access_denies_when_permission_explicitly_denied():
    """Test enforce access denies when permission explicitly denied.

    Returns:
        The function result.
    """
    with pytest.raises(HTTPException) as exc:
        _enforce_access(
            _u(permissions=["report:preview"], denied=["report:preview"]),
            permission="report:preview",
        )
    assert exc.value.status_code == 403


def test_enforce_access_allows_min_level():
    """Test enforce access allows min level.

    Returns:
        The function result.
    """
    _enforce_access(_u(level=10), min_level=9)


def test_enforce_access_denies_insufficient_level():
    """Test enforce access denies insufficient level.

    Returns:
        The function result.
    """
    with pytest.raises(HTTPException) as exc:
        _enforce_access(_u(level=2), min_level=9)
    assert exc.value.status_code == 403


def test_enforce_access_allows_min_role(monkeypatch):
    # manager role threshold resolved to level 50
    """Test enforce access allows min role.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr("api.security.access._role_levels", lambda: {"manager": 50})
    _enforce_access(_u(role="manager", level=55), min_role="manager")


def test_enforce_access_denies_when_no_constraint_matches(monkeypatch):
    """Test enforce access denies when no constraint matches.

    Args:
        monkeypatch: Value for ``monkeypatch``.

    Returns:
        The function result.
    """
    monkeypatch.setattr("api.security.access._role_levels", lambda: {"manager": 50})
    with pytest.raises(HTTPException) as exc:
        _enforce_access(
            _u(level=10, permissions=[]),
            permission="report:create",
            min_level=99,
            min_role="manager",
        )
    assert exc.value.status_code == 403


def test_enforce_access_superuser_bypasses_all_checks():
    """Superuser should bypass all permission, level, and role checks."""
    _enforce_access(
        _u(role="superuser", level=0, permissions=[]),
        permission="permission.policy:delete",
        min_level=999999,
        min_role="superuser",
    )


def test_get_sample_for_api_returns_specific_scope_error(monkeypatch):
    """Sample lookup should explain assay-scope denials clearly."""
    user = _u(role="user", level=9, permissions=["sample:view:own"])
    user.assays = ["WGS"]
    sample = {"_id": "s1", "name": "S1", "assay": "hema_GMSv1"}

    monkeypatch.setattr(
        "api.security.access.get_sample_handler",
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
