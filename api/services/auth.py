"""Authentication service helpers for FastAPI routes."""

from __future__ import annotations

from api.runtime import app

from api.extensions import ldap_manager, store
from api.models.user import UserModel


def _ldap_authenticate(username: str, password: str) -> bool:
    return bool(
        ldap_manager.authenticate(
            username=username,
            password=password,
            base_dn=app.config.get("LDAP_BASE_DN") or app.config.get("LDAP_BINDDN"),
            attribute=app.config.get("LDAP_USER_LOGIN_ATTR"),
        )
    )


def build_user_session_payload(user_doc: dict) -> dict:
    role_doc = store.roles_handler.get_role(user_doc.get("role")) or {}
    asp_docs = store.asp_handler.get_all_asps(is_active=True)
    user_model = UserModel.from_mongo(user_doc, role_doc, asp_docs)
    return user_model.to_dict()


def authenticate_credentials(username: str, password: str) -> dict | None:
    user_doc = store.user_handler.user(username)
    if not user_doc or not user_doc.get("is_active", True):
        return None

    use_internal = user_doc.get("auth_type") == "coyote3"
    valid = (
        UserModel.validate_login(user_doc.get("password", ""), password)
        if use_internal
        else _ldap_authenticate(username, password)
    )
    if not valid:
        return None
    return user_doc
