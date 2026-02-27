"""Dashboard API client mixin methods."""

from __future__ import annotations

from typing import Any

from coyote.integrations.api.base import ApiPayload


class DashboardApiClientMixin:
    def get_dashboard_summary(
        self, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get("/api/v1/dashboard/summary", headers=headers)
        return payload

