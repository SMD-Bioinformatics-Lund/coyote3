"""Authentication service helpers for FastAPI routes."""

from __future__ import annotations

from typing import Any

from api.app.container import ldap_manager
from api.app.deps.repositories import (
    get_assay_panel_repository,
    get_roles_repository,
    get_user_repository,
)
from api.app.runtime_state import app
from api.config.constants import (
    AUTH_PROVIDER_LDAP,
    AUTH_PROVIDER_LOCAL,
    DEFAULT_AUTH_PROVIDER,
    normalize_auth_types,
)
from api.domain.core.models.user import UserModel
from api.infra.observability.auth_metrics import emit_auth_metric


def _login_provider(login_identifier: str) -> str:
    """Return provider selected by submitted login identifier."""
    provider = AUTH_PROVIDER_LDAP if "@" in str(login_identifier or "") else AUTH_PROVIDER_LOCAL
    return str(provider)


def _lookup_user_doc(
    login_identifier: str, *, provider: str | None = None
) -> dict[str, Any] | None:
    """Lookup user doc by provider-specific login key.

    Args:
            login_identifier: Login identifier.

    Returns:
            The  lookup user doc result.
    """
    normalized = str(login_identifier).strip().lower()
    if not normalized:
        return None
    user_repository = get_user_repository()
    selected_provider = provider or _login_provider(normalized)
    if selected_provider == AUTH_PROVIDER_LDAP:
        result = user_repository.user_by_email(normalized)
    elif selected_provider == AUTH_PROVIDER_LOCAL:
        result = user_repository.user_by_username(normalized)
    else:
        return None
    return dict(result) if isinstance(result, dict) else None


def _load_user_access_context(
    user_doc: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return the role documents and active assay panels for a user document."""
    roles_repository = get_roles_repository()
    role_docs = [
        dict(role_doc)
        for role_id in (user_doc.get("roles") or [])
        if (role_doc := roles_repository.get_role(role_id)) and isinstance(role_doc, dict)
    ]
    assay_panels = [
        dict(item)
        for item in (get_assay_panel_repository().get_all_asps(is_active=True) or [])
        if isinstance(item, dict)
    ]
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


def build_user_session_payload(user_doc: dict[str, Any]) -> dict[str, Any]:
    """Build the canonical API session payload for a user document.

    Args:
        user_doc: Authenticated user document loaded from persistence.

    Returns:
        The normalized session payload returned to API clients.
    """
    role_docs, asp_docs = _load_user_access_context(user_doc)
    user_model = UserModel.from_auth_payload(user_doc, role_docs, asp_docs)
    payload = user_model.to_dict()
    return dict(payload) if isinstance(payload, dict) else {}


def resolve_user_identity(user_doc: dict[str, Any]) -> str:
    """Return the canonical user identity for session and update flows.

    Args:
        user_doc: Authenticated user document loaded from persistence.

    Returns:
        The canonical username string for the user.
    """
    return str(user_doc.get("username") or "").strip()


def authenticate_credentials(
    username: str,
    password: str,
    *,
    provider: str | None = None,
) -> dict[str, Any] | None:
    """Authenticate a username/password pair against local or LDAP auth.

    Args:
        username: Submitted login identifier.
        password: Submitted password.

    Returns:
        The authenticated user document, or ``None`` when authentication fails.
    """
    selected_provider = provider or _login_provider(username)
    user_doc = _lookup_user_doc(username, provider=selected_provider)
    if not user_doc:
        emit_auth_metric("login_attempt", outcome="failed", reason="user_not_found")
        return None
    if not user_doc.get("is_active", True):
        emit_auth_metric("login_attempt", outcome="failed", reason="inactive_user")
        return None

    auth_types = normalize_auth_types(user_doc.get("auth_type") or [DEFAULT_AUTH_PROVIDER])
    if selected_provider not in auth_types:
        emit_auth_metric(
            "login_attempt",
            outcome="failed",
            auth_type=selected_provider,
            reason="provider_not_enabled",
        )
        return None
    use_internal = selected_provider == AUTH_PROVIDER_LOCAL
    valid = (
        UserModel.validate_login(user_doc.get("password", ""), password)
        if use_internal
        else _ldap_authenticate(username, password)
    )
    if not valid:
        emit_auth_metric(
            "login_attempt",
            outcome="failed",
            auth_type=selected_provider,
            reason="invalid_credentials",
        )
        return None
    emit_auth_metric("login_attempt", outcome="success", auth_type=selected_provider)
    return user_doc


def update_user_last_login(user_id: str) -> None:
    """Persist the last-login timestamp for a user.

    Args:
        user_id: User identifier being updated.

    Returns:
        ``None``.
    """
    get_user_repository().update_user_last_login(user_id)
