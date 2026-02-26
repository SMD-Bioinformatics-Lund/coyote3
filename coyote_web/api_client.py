"""Server-side API client used by Flask web routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from flask import current_app

from coyote_web.api_models import (
    ApiMutationResultPayload,
    ApiDnaCnvsPayload,
    ApiDnaCnvDetailPayload,
    ApiDnaReportPreviewPayload,
    ApiDnaReportSavePayload,
    ApiDnaTranslocationsPayload,
    ApiDnaVariantDetailPayload,
    ApiDnaVariantsPayload,
    ApiDnaTranslocationDetailPayload,
    ApiRnaFusionDetailPayload,
    ApiRnaFusionsPayload,
    ApiRnaReportPreviewPayload,
    ApiRnaReportSavePayload,
)


@dataclass
class ApiRequestError(Exception):
    message: str
    status_code: int | None = None
    payload: Any | None = None

    def __str__(self) -> str:
        return self.message


class CoyoteApiClient:
    def __init__(self, base_url: str, timeout_seconds: float = 30.0) -> None:
        self._base_url = str(base_url).rstrip("/")
        self._timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers or {},
                    params=params or None,
                )
        except httpx.RequestError as exc:
            raise ApiRequestError(message=f"API request failed: {exc}") from exc

        try:
            payload = response.json()
        except Exception:
            payload = {"error": response.text}

        if response.status_code >= 400:
            message = payload.get("error", f"API request failed ({response.status_code})")
            raise ApiRequestError(message=message, status_code=response.status_code, payload=payload)

        if not isinstance(payload, dict):
            raise ApiRequestError(
                message="API returned invalid payload format.",
                status_code=response.status_code,
                payload=payload,
            )
        return payload

    def _get(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request("GET", path, headers=headers, params=params)

    def _post(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request("POST", path, headers=headers, params=params)

    def get_rna_fusions(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiRnaFusionsPayload:
        payload = self._get(f"/api/v1/rna/samples/{sample_id}/fusions", headers=headers)
        return ApiRnaFusionsPayload.model_validate(payload)

    def get_dna_variants(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiDnaVariantsPayload:
        payload = self._get(f"/api/v1/dna/samples/{sample_id}/variants", headers=headers)
        return ApiDnaVariantsPayload.model_validate(payload)

    def get_rna_fusion(
        self, sample_id: str, fusion_id: str, headers: dict[str, str] | None = None
    ) -> ApiRnaFusionDetailPayload:
        payload = self._get(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}",
            headers=headers,
        )
        return ApiRnaFusionDetailPayload.model_validate(payload)

    def get_dna_variant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiDnaVariantDetailPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}",
            headers=headers,
        )
        return ApiDnaVariantDetailPayload.model_validate(payload)

    def get_dna_cnv(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiDnaCnvDetailPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}",
            headers=headers,
        )
        return ApiDnaCnvDetailPayload.model_validate(payload)

    def get_dna_translocation(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiDnaTranslocationDetailPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}",
            headers=headers,
        )
        return ApiDnaTranslocationDetailPayload.model_validate(payload)

    def get_dna_cnvs(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiDnaCnvsPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/cnvs",
            headers=headers,
        )
        return ApiDnaCnvsPayload.model_validate(payload)

    def get_dna_translocations(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiDnaTranslocationsPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/translocations",
            headers=headers,
        )
        return ApiDnaTranslocationsPayload.model_validate(payload)

    def get_dna_report_preview(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiDnaReportPreviewPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/report/preview",
            headers=headers,
        )
        return ApiDnaReportPreviewPayload.model_validate(payload)

    def get_rna_report_preview(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiRnaReportPreviewPayload:
        payload = self._get(
            f"/api/v1/rna/samples/{sample_id}/report/preview",
            headers=headers,
        )
        return ApiRnaReportPreviewPayload.model_validate(payload)

    def save_dna_report(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiDnaReportSavePayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/report/save",
            headers=headers,
        )
        return ApiDnaReportSavePayload.model_validate(payload)

    def save_rna_report(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiRnaReportSavePayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/report/save",
            headers=headers,
        )
        return ApiRnaReportSavePayload.model_validate(payload)

    def mark_dna_cnv_interesting(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/interesting", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def unmark_dna_cnv_interesting(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unmarkinteresting",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def mark_dna_cnv_false_positive(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/fpcnv", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def unmark_dna_cnv_false_positive(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unfpcnv", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def mark_dna_cnv_noteworthy(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/noteworthycnv",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def unmark_dna_cnv_noteworthy(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/notnoteworthycnv",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def hide_dna_cnv_comment(
        self, sample_id: str, cnv_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def unhide_dna_cnv_comment(
        self, sample_id: str, cnv_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def mark_dna_translocation_interesting(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/interestingtransloc",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def unmark_dna_translocation_interesting(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/uninterestingtransloc",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def mark_dna_translocation_false_positive(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/fptransloc",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def unmark_dna_translocation_false_positive(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/ptransloc",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def hide_dna_translocation_comment(
        self, sample_id: str, transloc_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def unhide_dna_translocation_comment(
        self, sample_id: str, transloc_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def mark_dna_variant_false_positive(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/fp", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def unmark_dna_variant_false_positive(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/unfp", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def mark_dna_variant_interesting(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/interest", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def unmark_dna_variant_interesting(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/uninterest",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def mark_dna_variant_irrelevant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/irrelevant",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def unmark_dna_variant_irrelevant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/relevant",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def blacklist_dna_variant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/blacklist", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def hide_dna_variant_comment(
        self, sample_id: str, var_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def unhide_dna_variant_comment(
        self, sample_id: str, var_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def set_dna_variants_false_positive_bulk(
        self,
        sample_id: str,
        variant_ids: list[str],
        apply: bool,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/bulk/fp",
            headers=headers,
            params={"apply": str(bool(apply)).lower(), "variant_ids": variant_ids},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def set_dna_variants_irrelevant_bulk(
        self,
        sample_id: str,
        variant_ids: list[str],
        apply: bool,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/bulk/irrelevant",
            headers=headers,
            params={"apply": str(bool(apply)).lower(), "variant_ids": variant_ids},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def mark_rna_fusion_false_positive(
        self, sample_id: str, fusion_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/fp", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def unmark_rna_fusion_false_positive(
        self, sample_id: str, fusion_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/unfp",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def pick_rna_fusion_call(
        self,
        sample_id: str,
        fusion_id: str,
        callidx: str,
        num_calls: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/pick/{callidx}/{num_calls}",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def hide_rna_fusion_comment(
        self, sample_id: str, fusion_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def unhide_rna_fusion_comment(
        self, sample_id: str, fusion_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def set_rna_fusions_false_positive_bulk(
        self,
        sample_id: str,
        fusion_ids: list[str],
        apply: bool,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/bulk/fp",
            headers=headers,
            params={"apply": str(bool(apply)).lower(), "fusion_ids": fusion_ids},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def set_rna_fusions_irrelevant_bulk(
        self,
        sample_id: str,
        fusion_ids: list[str],
        apply: bool,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/rna/samples/{sample_id}/fusions/bulk/irrelevant",
            headers=headers,
            params={"apply": str(bool(apply)).lower(), "fusion_ids": fusion_ids},
        )
        return ApiMutationResultPayload.model_validate(payload)


def get_web_api_client() -> CoyoteApiClient:
    return CoyoteApiClient(base_url=current_app.config.get("API_BASE_URL", "http://127.0.0.1:8001"))


def build_forward_headers(request_headers: Any) -> dict[str, str]:
    cookie_header = request_headers.get("Cookie")
    headers = {"X-Requested-With": "XMLHttpRequest"}
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers
