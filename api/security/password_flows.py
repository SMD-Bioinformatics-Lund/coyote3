"""Password lifecycle helpers for local-auth users."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from api.extensions import util
from api.infra.notifications.email import send_email, smtp_configured
from api.runtime import app as runtime_app
from api.security.auth_service import _lookup_user_doc, resolve_user_identity
from api.security.repository import get_security_repository
from api.settings import get_api_secret_key

_TOKEN_PURPOSE_INVITE = "invite"
_TOKEN_PURPOSE_RESET = "reset"
_TOKEN_PURPOSES = {_TOKEN_PURPOSE_INVITE, _TOKEN_PURPOSE_RESET}


def _password_token_ttl_seconds() -> int:
    try:
        return int(runtime_app.config.get("PASSWORD_TOKEN_TTL_SECONDS", 60 * 60))
    except Exception:
        return 60 * 60


def _password_token_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(
        secret_key=get_api_secret_key(runtime_app.config),
        salt=str(runtime_app.config.get("PASSWORD_TOKEN_SALT", "coyote3-password-token-v1")),
    )


def _token_hash(token: str) -> str:
    return hashlib.sha256(str(token).encode("utf-8")).hexdigest()


def _is_local_user(user_doc: dict[str, Any]) -> bool:
    auth_type = str(user_doc.get("auth_type") or "coyote3").strip().lower()
    return auth_type == "coyote3"


def _build_set_password_url(token: str) -> str:
    base = str(runtime_app.config.get("WEB_APP_BASE_URL") or "").strip().rstrip("/")
    path = f"/reset-password?token={token}"
    return f"{base}{path}" if base else path


def _issue_token(*, user_id: str, purpose: str) -> str:
    return str(
        _password_token_serializer().dumps(
            {"uid": user_id, "purpose": purpose, "nonce": secrets.token_urlsafe(16)}
        )
    )


def issue_password_token_for_user(
    *, login_identifier: str, purpose: str, actor_username: str | None = None
) -> dict[str, Any]:
    """Issue a password action token for a local user.

    Returns a neutral response for unsupported/missing users to avoid account
    enumeration behavior on public flows.
    """
    if purpose not in _TOKEN_PURPOSES:
        raise ValueError(f"Unsupported password token purpose: {purpose}")

    user_doc = _lookup_user_doc(login_identifier)
    if not user_doc or not user_doc.get("is_active", True) or not _is_local_user(user_doc):
        return {"status": "ok", "email_sent": False, "mail_configured": bool(smtp_configured())}

    user_id = resolve_user_identity(user_doc)
    if not user_id:
        return {"status": "ok", "email_sent": False, "mail_configured": bool(smtp_configured())}

    token = _issue_token(user_id=user_id, purpose=purpose)
    expiry = datetime.now(timezone.utc) + timedelta(seconds=_password_token_ttl_seconds())
    repo = get_security_repository()
    repo.set_user_password_token(
        user_id=user_id,
        token_hash=_token_hash(token),
        purpose=purpose,
        expires_at=expiry,
        issued_by=actor_username,
    )

    to_email = str(user_doc.get("email") or "").strip()
    setup_url = _build_set_password_url(token)
    ttl_minutes = max(1, int(_password_token_ttl_seconds() / 60))
    subject = (
        "Coyote3 account setup" if purpose == _TOKEN_PURPOSE_INVITE else "Coyote3 password reset"
    )
    text_body = (
        "A password action was requested for your Coyote3 account.\n\n"
        f"Use this link: {setup_url}\n"
        f"This link expires in {ttl_minutes} minutes.\n\n"
        "If you did not expect this, contact your administrator."
    )
    mail_ready = bool(smtp_configured())
    email_sent = (
        send_email(to_email=to_email, subject=subject, text_body=text_body) if to_email else False
    )
    warning: str | None = None
    if not mail_ready:
        warning = "Mail is not configured. Share the setup URL manually."
    elif not email_sent:
        warning = "Mail send failed. Share the setup URL manually."
    return {
        "status": "ok",
        "email_sent": bool(email_sent),
        "mail_configured": mail_ready,
        "setup_url": setup_url,
        "expires_in_seconds": _password_token_ttl_seconds(),
        "warning": warning,
    }


def _decode_password_token(token: str) -> dict[str, Any] | None:
    try:
        return _password_token_serializer().loads(
            token,
            max_age=_password_token_ttl_seconds(),
        )
    except (BadSignature, SignatureExpired):
        return None


def consume_password_token_and_set_password(*, token: str, new_password: str) -> dict[str, Any]:
    """Validate/consume one-time token and set local password."""
    token_data = _decode_password_token(str(token or "").strip())
    if not token_data:
        return {"status": "error", "error": "Invalid or expired token"}

    user_id = str(token_data.get("uid") or "").strip().lower()
    purpose = str(token_data.get("purpose") or "").strip().lower()
    if not user_id or purpose not in _TOKEN_PURPOSES:
        return {"status": "error", "error": "Invalid token payload"}

    repo = get_security_repository()
    user_doc = repo.get_user_by_id(user_id)
    if not user_doc or not user_doc.get("is_active", True) or not _is_local_user(user_doc):
        return {"status": "error", "error": "Invalid token user"}

    if not repo.validate_and_clear_password_token(
        user_id=user_id,
        token_hash=_token_hash(token),
        purpose=purpose,
    ):
        return {"status": "error", "error": "Token already used or expired"}

    repo.set_local_password(
        user_id=user_id,
        password_hash=util.common.hash_password(new_password),
        require_password_change=False,
    )
    return {"status": "ok", "username": user_id}


def change_local_password(
    *, user_id: str, current_password: str, new_password: str
) -> dict[str, Any]:
    """Change password for an already authenticated local user."""
    repo = get_security_repository()
    user_doc = repo.get_user_by_id(user_id)
    if not user_doc or not user_doc.get("is_active", True):
        return {"status": "error", "error": "User not found"}

    if not _is_local_user(user_doc):
        return {"status": "error", "error": "Password is managed by external identity provider"}

    from api.domain.models.user import UserModel

    if not UserModel.validate_login(str(user_doc.get("password") or ""), current_password):
        return {"status": "error", "error": "Current password is incorrect"}

    repo.set_local_password(
        user_id=user_id,
        password_hash=util.common.hash_password(new_password),
        require_password_change=False,
    )
    return {"status": "ok", "username": user_id}
