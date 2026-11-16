"""Synthetic reusable fixtures for package-owned behavior tests."""

from types import SimpleNamespace

from coyote_api.security import access


def user_session(monkeypatch, permissions):
    """Provide a resolved user session while retaining real permission enforcement."""
    user = access.ApiUser(
        id="synthetic-issuer",
        username="issuer",
        email="",
        fullname="Issuer",
        role="issuer",
        access_level=0,
        asp_ids=[],
        asp_groups=[],
        asp_map={},
        auth_type=["local"],
        permissions=permissions,
        roles=["issuer"],
        envs=["development"],
    )
    monkeypatch.setattr(
        access,
        "get_roles_repository",
        lambda: SimpleNamespace(
            get_all_roles=lambda: [
                {"role_id": "issuer", "is_active": True, "permissions": permissions}
            ]
        ),
    )
    monkeypatch.setattr(
        access, "_get_cached_api_session", lambda request, token: SimpleNamespace(user=user)
    )
    monkeypatch.setattr(access, "_enforce_password_change", lambda user, request: None)
