"""Internal API client mixin methods."""

from __future__ import annotations

from typing import Any

from coyote.integrations.api.base import ApiPayload


class InternalApiClientMixin:
    def get_isgl_meta_internal(
        self,
        isgl_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/internal/isgl/{isgl_id}/meta",
            headers=headers,
        )
        return payload

    def get_role_levels_internal(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(
            "/api/v1/internal/roles/levels",
            headers=headers,
        )
        return payload

