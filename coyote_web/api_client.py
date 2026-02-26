"""Server-side API client used by Flask web routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from flask import current_app

from coyote_web.api_models import (
    ApiDnaCnvDetailPayload,
    ApiDnaVariantDetailPayload,
    ApiDnaVariantsPayload,
    ApiDnaTranslocationDetailPayload,
    ApiRnaFusionDetailPayload,
    ApiRnaFusionsPayload,
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

    def _get(self, path: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.get(url, headers=headers or {})
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


def get_web_api_client() -> CoyoteApiClient:
    return CoyoteApiClient(base_url=current_app.config.get("API_BASE_URL", "http://127.0.0.1:8001"))


def build_forward_headers(request_headers: Any) -> dict[str, str]:
    cookie_header = request_headers.get("Cookie")
    headers = {"X-Requested-With": "XMLHttpRequest"}
    if cookie_header:
        headers["Cookie"] = cookie_header
    return headers
