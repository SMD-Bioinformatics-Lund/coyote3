"""Common API client mixin methods."""

from __future__ import annotations

from typing import Any

from coyote.integrations.api.base import ApiPayload


class CommonApiClientMixin:
    def get_common_gene_info(
        self, gene_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/common/gene/{gene_id}/info", headers=headers)
        return payload

    def get_common_tiered_variant_context(
        self, variant_id: str, tier: int, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/common/reported_variants/variant/{variant_id}/{tier}",
            headers=headers,
        )
        return payload

    def search_common_tiered_variants(
        self,
        search_str: str | None = None,
        search_mode: str | None = None,
        include_annotation_text: bool = False,
        assays: list[str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params: dict[str, Any] = {}
        if search_str:
            params["search_str"] = search_str
        if search_mode:
            params["search_mode"] = search_mode
        params["include_annotation_text"] = str(bool(include_annotation_text)).lower()
        if assays:
            params["assays"] = assays
        payload = self._get("/api/v1/common/search/tiered_variants", headers=headers, params=params)
        return payload

    def add_sample_comment(
        self,
        sample_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/samples/{sample_id}/sample_comments/add",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return payload

    def hide_sample_comment(
        self,
        sample_id: str,
        comment_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/samples/{sample_id}/sample_comments/{comment_id}/hide",
            headers=headers,
        )
        return payload

    def unhide_sample_comment(
        self,
        sample_id: str,
        comment_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/samples/{sample_id}/sample_comments/{comment_id}/unhide",
            headers=headers,
        )
        return payload

    def update_sample_filters(
        self,
        sample_id: str,
        filters: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/samples/{sample_id}/filters/update",
            headers=headers,
            json_body={"filters": filters},
        )
        return payload

    def reset_sample_filters(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/samples/{sample_id}/filters/reset",
            headers=headers,
        )
        return payload

