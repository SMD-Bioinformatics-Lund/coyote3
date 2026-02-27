"""Rna API client mixin methods."""

from __future__ import annotations

from typing import Any

from coyote.integrations.api.base import ApiPayload


class RnaApiClientMixin:
    def get_rna_fusions(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/rna/samples/{sample_id}/fusions", headers=headers)
        return payload

    def get_rna_fusion(
        self, sample_id: str, fusion_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}",
            headers=headers,
        )
        return payload

    def get_rna_report_preview(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/rna/samples/{sample_id}/report/preview",
            headers=headers,
        )
        return payload

    def save_rna_report(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/report/save",
            headers=headers,
        )
        return payload

    def mark_rna_fusion_false_positive(
        self, sample_id: str, fusion_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/fp", headers=headers)
        return payload

    def unmark_rna_fusion_false_positive(
        self, sample_id: str, fusion_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/unfp",
            headers=headers,
        )
        return payload

    def pick_rna_fusion_call(
        self,
        sample_id: str,
        fusion_id: str,
        callidx: str,
        num_calls: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/pick/{callidx}/{num_calls}",
            headers=headers,
        )
        return payload

    def hide_rna_fusion_comment(
        self, sample_id: str, fusion_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return payload

    def unhide_rna_fusion_comment(
        self, sample_id: str, fusion_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return payload

    def set_rna_fusions_false_positive_bulk(
        self,
        sample_id: str,
        fusion_ids: list[str],
        apply: bool,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/bulk/fp",
            headers=headers,
            params={"apply": str(bool(apply)).lower(), "fusion_ids": fusion_ids},
        )
        return payload

    def set_rna_fusions_irrelevant_bulk(
        self,
        sample_id: str,
        fusion_ids: list[str],
        apply: bool,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/bulk/irrelevant",
            headers=headers,
            params={"apply": str(bool(apply)).lower(), "fusion_ids": fusion_ids},
        )
        return payload

