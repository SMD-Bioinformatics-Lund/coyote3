"""Authentication service helpers for FastAPI routes."""

from __future__ import annotations

from api.core.models.user import UserModel
from api.deps.handlers import get_assay_panel_handler, get_roles_handler, get_user_handler
from api.extensions import ldap_manager
from api.observability.auth_metrics import emit_auth_metric
from api.runtime_state import app


def _lookup_user_doc(login_identifier: str) -> dict | None:
    """Lookup user doc.

    Args:
            login_identifier: Login identifier.

    Returns:
            The  lookup user doc result.
    """
    normalized = str(login_identifier).strip().lower()
    if not normalized:
        return None
    user_handler = get_user_handler()
    return user_handler.user(normalized)


def _load_user_access_context(user_doc: dict) -> tuple[list[dict], list[dict]]:
    """Return the role documents and active assay panels for a user document."""
    roles_handler = get_roles_handler()
    role_docs = [
        role_doc
        for role_id in (user_doc.get("roles") or [])
        if (role_doc := roles_handler.get_role(role_id))
    ]
    assay_panels = list(get_assay_panel_handler().get_all_asps(is_active=True) or [])
    return role_docs, assay_panels


def _ldap_authenticate(username: str, password: str) -> bool:
    """Ldap authenticate.

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
    role_docs, asp_docs = _load_user_access_context(user_doc)
    user_model = UserModel.from_auth_payload(user_doc, role_docs, asp_docs)
    return user_model.to_dict()


def resolve_user_identity(user_doc: dict) -> str:
    """Return the canonical user identity for session and update flows.

    Args:
        user_doc: Authenticated user document loaded from persistence.

    Returns:
        The canonical username string for the user.
    """
    return str(user_doc.get("username") or "").strip()


def authenticate_credentials(username: str, password: str) -> dict | None:
    """Authenticate a username/password pair against local or LDAP auth.

    Args:
        username: Submitted login identifier.
        password: Submitted password.

    Returns:
        The authenticated user document, or ``None`` when authentication fails.
    """
    user_doc = _lookup_user_doc(username)
    if not user_doc:
        emit_auth_metric("login_attempt", outcome="failed", reason="user_not_found")
        return None
    if not user_doc.get("is_active", True):
        emit_auth_metric("login_attempt", outcome="failed", reason="inactive_user")
        return None

    auth_type = str(user_doc.get("auth_type") or "coyote3").strip().lower()
    use_internal = auth_type == "coyote3"
    valid = (
        UserModel.validate_login(user_doc.get("password", ""), password)
        if use_internal
        else _ldap_authenticate(username, password)
    )
    if not valid:
        emit_auth_metric(
            "login_attempt", outcome="failed", auth_type=auth_type, reason="invalid_credentials"
        )
        return None
    emit_auth_metric("login_attempt", outcome="success", auth_type=auth_type)
    return user_doc


def update_user_last_login(user_id: str) -> None:
    """Persist the last-login timestamp for a user.

    Args:
        user_id: User identifier being updated.

    Returns:
        ``None``.
    """
    get_user_handler().update_user_last_login(user_id)
