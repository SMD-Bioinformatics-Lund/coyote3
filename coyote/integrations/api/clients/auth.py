"""Auth API client mixin methods."""

from __future__ import annotations

from typing import Any

from coyote.integrations.api.base import ApiPayload


class AuthApiClientMixin:
    def login_auth(
        self,
        username: str,
        password: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/auth/login",
            headers=headers,
            json_body={"username": username, "password": password},
        )
        return payload

    def logout_auth(
        self,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._post("/api/v1/auth/logout", headers=headers)

    def get_auth_me(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/auth/me", headers=headers)
        return payload

