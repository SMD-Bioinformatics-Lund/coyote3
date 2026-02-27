"""Home API client mixin methods."""

from __future__ import annotations

from typing import Any

from coyote.integrations.api.base import ApiPayload


class HomeApiClientMixin:
    def get_home_samples(
        self,
        *,
        status: str,
        search_str: str,
        search_mode: str,
        panel_type: str | None = None,
        panel_tech: str | None = None,
        assay_group: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params: dict[str, Any] = {
            "status": status,
            "search_str": search_str,
            "search_mode": search_mode,
        }
        if panel_type:
            params["panel_type"] = panel_type
        if panel_tech:
            params["panel_tech"] = panel_tech
        if assay_group:
            params["assay_group"] = assay_group
        payload = self._get("/api/v1/home/samples", headers=headers, params=params)
        return payload

    def get_home_isgls(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/home/samples/{sample_id}/isgls", headers=headers)
        return payload

    def get_home_effective_genes_all(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/home/samples/{sample_id}/effective_genes/all", headers=headers)
        return payload

    def get_home_edit_context(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/home/samples/{sample_id}/edit_context", headers=headers)
        return payload

    def get_home_report_context(
        self,
        sample_id: str,
        report_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/home/samples/{sample_id}/reports/{report_id}/context",
            headers=headers,
        )
        return payload

    def apply_home_isgl(
        self,
        sample_id: str,
        isgl_ids: list[str],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._post(
            f"/api/v1/home/samples/{sample_id}/genes/apply-isgl",
            headers=headers,
            json_body={"isgl_ids": isgl_ids},
        )

    def save_home_adhoc_genes(
        self,
        sample_id: str,
        genes: str,
        label: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload = {"genes": genes}
        if label:
            payload["label"] = label
        return self._post(
            f"/api/v1/home/samples/{sample_id}/adhoc_genes/save",
            headers=headers,
            json_body=payload,
        )

    def clear_home_adhoc_genes(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        return self._post(
            f"/api/v1/home/samples/{sample_id}/adhoc_genes/clear",
            headers=headers,
        )

