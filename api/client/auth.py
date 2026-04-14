"""Programmatic authentication helpers for Coyote3 API consumers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class ApiLoginSession:
    """Represent authenticated session details for API callers."""

    base_url: str
    user: dict[str, Any]
    session_token: str | None = None
    cookie_name: str = "coyote3_api_session"

    @property
    def bearer_headers(self) -> dict[str, str]:
        """Return Authorization header map when token is available."""
        if not self.session_token:
            return {}
        return {"Authorization": f"Bearer {self.session_token}"}

    @property
    def cookie_headers(self) -> dict[str, str]:
        """Return Cookie header map when token is available."""
        if not self.session_token:
            return {}
        return {"Cookie": f"{self.cookie_name}={self.session_token}"}


def _normalize_base_url(base_url: str) -> str:
    return base_url.rstrip("/")


def _extract_session_token(response: httpx.Response, cookie_name: str) -> str | None:
    token = response.cookies.get(cookie_name)
    if token:
        return token
    if response.cookies:
        first = next(iter(response.cookies.items()), None)
        if first:
            return first[1]
    return None


def login_with_password(
    *,
    base_url: str,
    username: str,
    password: str,
    timeout: float = 30.0,
    cookie_name: str = "coyote3_api_session",
) -> ApiLoginSession:
    """Authenticate with username/password and return session details."""
    normalized = _normalize_base_url(base_url)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(
            f"{normalized}/api/v1/auth/sessions",
            json={"username": username, "password": password},
        )
        response.raise_for_status()
        body = response.json()
    return ApiLoginSession(
        base_url=normalized,
        user=body.get("user", {}),
        session_token=_extract_session_token(response, cookie_name),
        cookie_name=cookie_name,
    )


def login_with_token(
    *,
    base_url: str,
    token: str,
    timeout: float = 30.0,
    cookie_name: str = "coyote3_api_session",
) -> ApiLoginSession:
    """Validate an existing token and return session details."""
    normalized = _normalize_base_url(base_url)
    with httpx.Client(timeout=timeout) as client:
        response = client.get(
            f"{normalized}/api/v1/auth/session",
            headers={"Authorization": f"Bearer {token}"},
        )
        response.raise_for_status()
        body = response.json()
    return ApiLoginSession(
        base_url=normalized,
        user=body.get("user", {}),
        session_token=token,
        cookie_name=cookie_name,
    )
