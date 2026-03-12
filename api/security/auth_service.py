"""Authentication service helpers for FastAPI routes."""

from __future__ import annotations

from api.runtime import app

from api.extensions import ldap_manager
from api.domain.models.user import UserModel
from api.security.repository import get_security_repository


def _lookup_user_doc(login_identifier: str) -> dict | None:
    """Handle  lookup user doc.

    Args:
            login_identifier: Login identifier.

    Returns:
            The  lookup user doc result.
    """
    repo = get_security_repository()
    normalized = str(login_identifier).strip()
    if not normalized:
        return None
    user_doc = repo.get_user_by_username(normalized)
    if user_doc:
        return user_doc
    # Support explicit business-key lookup in addition to email/username.
    return repo.get_user_by_id(normalized)


def _is_local_auth_allowlisted(login_identifier: str, user_doc: dict) -> bool:
    """Handle  is local auth allowlisted.

    Args:
            login_identifier: Login identifier.
            user_doc: User doc.

    Returns:
            The  is local auth allowlisted result.
    """
    allowlist = app.config.get("LOCAL_AUTH_USER_IDENTIFIERS") or ()
    if not allowlist:
        return False

    allow = {str(item).strip().lower() for item in allowlist if str(item).strip()}
    candidates = {
        str(login_identifier).strip().lower(),
        str(user_doc.get("user_id") or "").strip().lower(),
        str(user_doc.get("username") or "").strip().lower(),
        str(user_doc.get("email") or "").strip().lower(),
    }
    return bool(candidates & allow)


def _ldap_authenticate(username: str, password: str) -> bool:
    """Handle  ldap authenticate.

    Args:
            username: Username.
            password: Password.

    Returns:
            The  ldap authenticate result.
    """
    return bool(
        ldap_manager.authenticate(
            username=username,
            password=password,
            base_dn=app.config.get("LDAP_BASE_DN") or app.config.get("LDAP_BINDDN"),
            attribute=app.config.get("LDAP_USER_LOGIN_ATTR"),
        )
    )


def build_user_session_payload(user_doc: dict) -> dict:
    """Build the canonical API session payload for a user document.

    Args:
        user_doc: Authenticated user document loaded from persistence.

    Returns:
        The normalized session payload returned to API clients.
    """
    repo = get_security_repository()
    role_doc = repo.get_role(user_doc.get("role")) or {}
    asp_docs = repo.get_all_active_asps()
    user_model = UserModel.from_mongo(user_doc, role_doc, asp_docs)
    return user_model.to_dict()


def resolve_user_identity(user_doc: dict) -> str:
    """Return the canonical user identity for session and update flows.

    Args:
        user_doc: Authenticated user document loaded from persistence.

    Returns:
        The canonical ``user_id`` string for the user.
    """
    return str(user_doc.get("user_id") or "").strip()


def authenticate_credentials(username: str, password: str) -> dict | None:
    """Authenticate a username/password pair against local or LDAP auth.

    Args:
        username: Submitted login identifier.
        password: Submitted password.

    Returns:
        The authenticated user document, or ``None`` when authentication fails.
    """
    user_doc = _lookup_user_doc(username)
    if not user_doc or not user_doc.get("is_active", True):
        return None

    use_internal = user_doc.get("auth_type") == "coyote3" or _is_local_auth_allowlisted(
        username, user_doc
    )
    valid = (
        UserModel.validate_login(user_doc.get("password", ""), password)
        if use_internal
        else _ldap_authenticate(username, password)
    )
    if not valid:
        return None
    return user_doc


def update_user_last_login(user_id: str) -> None:
    """Persist the last-login timestamp for a user.

    Args:
        user_id: User identifier being updated.

    Returns:
        ``None``.
    """
    get_security_repository().update_user_last_login(user_id)
