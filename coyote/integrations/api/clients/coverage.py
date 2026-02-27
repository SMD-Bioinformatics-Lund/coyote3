"""Coverage API client mixin methods."""

from __future__ import annotations

from typing import Any

from coyote.integrations.api.base import ApiPayload


class CoverageApiClientMixin:
    def get_coverage_sample(
        self,
        sample_id: str,
        cov_cutoff: int = 500,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/coverage/samples/{sample_id}",
            headers=headers,
            params={"cov_cutoff": cov_cutoff},
        )
        return payload

    def get_coverage_blacklisted(
        self,
        group: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/coverage/blacklisted/{group}", headers=headers)
        return payload

    def update_coverage_blacklist(
        self,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "/api/v1/coverage/blacklist/update",
            headers=headers,
            json_body=payload,
        )

    def remove_coverage_blacklist(
        self,
        obj_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/coverage/blacklist/{obj_id}/remove", headers=headers)
        return payload

