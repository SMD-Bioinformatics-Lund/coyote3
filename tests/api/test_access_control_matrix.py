"""Access-control matrix tests for role/level/permission behavior."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.security.access import ApiUser, _enforce_access


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
    _enforce_access(_u(permissions=["preview_report"]), permission="preview_report")


def test_enforce_access_denies_when_permission_explicitly_denied():
    """Test enforce access denies when permission explicitly denied.

    Returns:
        The function result.
    """
    with pytest.raises(HTTPException) as exc:
        _enforce_access(
            _u(permissions=["preview_report"], denied=["preview_report"]),
            permission="preview_report",
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
            permission="create_report",
            min_level=99,
            min_role="manager",
        )
    assert exc.value.status_code == 403
