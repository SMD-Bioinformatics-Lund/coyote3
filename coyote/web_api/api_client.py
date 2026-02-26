"""Server-side API client used by Flask web routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from flask import current_app

from coyote.web_api.api_models import (
    ApiAuthLoginPayload,
    ApiAuthSessionUserPayload,
    ApiDashboardSummaryPayload,
    ApiAdminPermissionContextPayload,
    ApiAdminPermissionCreateContextPayload,
    ApiAdminPermissionsPayload,
    ApiAdminGenelistContextPayload,
    ApiAdminGenelistCreateContextPayload,
    ApiAdminGenelistViewContextPayload,
    ApiAdminGenelistsPayload,
    ApiAdminAspContextPayload,
    ApiAdminAspCreateContextPayload,
    ApiAdminAspPayload,
    ApiAdminAspcContextPayload,
    ApiAdminAspcCreateContextPayload,
    ApiAdminAspcPayload,
    ApiAdminSampleContextPayload,
    ApiAdminSamplesPayload,
    ApiAdminRoleContextPayload,
    ApiAdminRoleCreateContextPayload,
    ApiAdminRolesPayload,
    ApiAdminSchemaContextPayload,
    ApiAdminSchemasPayload,
    ApiAdminUserContextPayload,
    ApiAdminUserCreateContextPayload,
    ApiAdminUsersPayload,
    ApiMutationResultPayload,
    ApiDnaBiomarkersPayload,
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
    ApiCommonGeneInfoPayload,
    ApiCommonTieredVariantPayload,
    ApiCommonTieredVariantSearchPayload,
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
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=self._timeout_seconds) as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers or {},
                    params=params or None,
                    json=json_body,
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
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request("POST", path, headers=headers, params=params, json_body=json_body)

    def get_rna_fusions(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiRnaFusionsPayload:
        payload = self._get(f"/api/v1/rna/samples/{sample_id}/fusions", headers=headers)
        return ApiRnaFusionsPayload.model_validate(payload)

    def get_dashboard_summary(
        self, headers: dict[str, str] | None = None
    ) -> ApiDashboardSummaryPayload:
        payload = self._get("/api/v1/dashboard/summary", headers=headers)
        return ApiDashboardSummaryPayload.model_validate(payload)

    def get_common_gene_info(
        self, gene_id: str, headers: dict[str, str] | None = None
    ) -> ApiCommonGeneInfoPayload:
        payload = self._get(f"/api/v1/common/gene/{gene_id}/info", headers=headers)
        return ApiCommonGeneInfoPayload.model_validate(payload)

    def get_common_tiered_variant_context(
        self, variant_id: str, tier: int, headers: dict[str, str] | None = None
    ) -> ApiCommonTieredVariantPayload:
        payload = self._get(
            f"/api/v1/common/reported_variants/variant/{variant_id}/{tier}",
            headers=headers,
        )
        return ApiCommonTieredVariantPayload.model_validate(payload)

    def search_common_tiered_variants(
        self,
        search_str: str | None = None,
        search_mode: str | None = None,
        include_annotation_text: bool = False,
        assays: list[str] | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiCommonTieredVariantSearchPayload:
        params: dict[str, Any] = {}
        if search_str:
            params["search_str"] = search_str
        if search_mode:
            params["search_mode"] = search_mode
        params["include_annotation_text"] = str(bool(include_annotation_text)).lower()
        if assays:
            params["assays"] = assays
        payload = self._get("/api/v1/common/search/tiered_variants", headers=headers, params=params)
        return ApiCommonTieredVariantSearchPayload.model_validate(payload)

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

    def get_dna_biomarkers(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiDnaBiomarkersPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/biomarkers",
            headers=headers,
        )
        return ApiDnaBiomarkersPayload.model_validate(payload)

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

    def set_dna_variants_tier_bulk(
        self,
        sample_id: str,
        variant_ids: list[str],
        assay_group: str | None,
        subpanel: str | None,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/bulk/tier",
            headers=headers,
            json_body={
                "variant_ids": variant_ids,
                "assay_group": assay_group,
                "subpanel": subpanel,
            },
        )
        return ApiMutationResultPayload.model_validate(payload)

    def classify_dna_variant(
        self,
        sample_id: str,
        target_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/classify",
            headers=headers,
            json_body={"id": target_id, "form_data": form_data},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def remove_dna_variant_classification(
        self,
        sample_id: str,
        target_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/rmclassify",
            headers=headers,
            json_body={"id": target_id, "form_data": form_data},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def add_dna_variant_comment(
        self,
        sample_id: str,
        target_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/comments/add",
            headers=headers,
            json_body={"id": target_id, "form_data": form_data},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def add_sample_comment(
        self,
        sample_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/samples/{sample_id}/sample_comments/add",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def hide_sample_comment(
        self,
        sample_id: str,
        comment_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/samples/{sample_id}/sample_comments/{comment_id}/hide",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def unhide_sample_comment(
        self,
        sample_id: str,
        comment_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/samples/{sample_id}/sample_comments/{comment_id}/unhide",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def update_sample_filters(
        self,
        sample_id: str,
        filters: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/samples/{sample_id}/filters/update",
            headers=headers,
            json_body={"filters": filters},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def reset_sample_filters(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/samples/{sample_id}/filters/reset",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def create_admin_permission(
        self,
        schema_id: str | None,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            "/api/v1/admin/permissions/create",
            headers=headers,
            json_body={"schema_id": schema_id, "form_data": form_data},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def get_admin_permissions(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminPermissionsPayload:
        payload = self._get("/api/v1/admin/permissions", headers=headers)
        return ApiAdminPermissionsPayload.model_validate(payload)

    def get_admin_permission_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminPermissionCreateContextPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/permissions/create_context", headers=headers, params=params)
        return ApiAdminPermissionCreateContextPayload.model_validate(payload)

    def get_admin_permission_context(
        self,
        perm_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminPermissionContextPayload:
        payload = self._get(f"/api/v1/admin/permissions/{perm_id}/context", headers=headers)
        return ApiAdminPermissionContextPayload.model_validate(payload)

    def update_admin_permission(
        self,
        perm_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/admin/permissions/{perm_id}/update",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def toggle_admin_permission(
        self,
        perm_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/permissions/{perm_id}/toggle", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def delete_admin_permission(
        self,
        perm_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/permissions/{perm_id}/delete", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def create_admin_schema(
        self,
        schema_doc: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            "/api/v1/admin/schemas/create",
            headers=headers,
            json_body={"schema": schema_doc},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def get_admin_schemas(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminSchemasPayload:
        payload = self._get("/api/v1/admin/schemas", headers=headers)
        return ApiAdminSchemasPayload.model_validate(payload)

    def get_admin_schema_context(
        self,
        schema_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminSchemaContextPayload:
        payload = self._get(f"/api/v1/admin/schemas/{schema_id}/context", headers=headers)
        return ApiAdminSchemaContextPayload.model_validate(payload)

    def update_admin_schema(
        self,
        schema_id: str,
        schema_doc: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/admin/schemas/{schema_id}/update",
            headers=headers,
            json_body={"schema": schema_doc},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def toggle_admin_schema(
        self,
        schema_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/schemas/{schema_id}/toggle", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def delete_admin_schema(
        self,
        schema_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/schemas/{schema_id}/delete", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def create_admin_role(
        self,
        schema_id: str | None,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            "/api/v1/admin/roles/create",
            headers=headers,
            json_body={"schema_id": schema_id, "form_data": form_data},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def get_admin_roles(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminRolesPayload:
        payload = self._get("/api/v1/admin/roles", headers=headers)
        return ApiAdminRolesPayload.model_validate(payload)

    def get_admin_role_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminRoleCreateContextPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/roles/create_context", headers=headers, params=params)
        return ApiAdminRoleCreateContextPayload.model_validate(payload)

    def get_admin_role_context(
        self,
        role_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminRoleContextPayload:
        payload = self._get(f"/api/v1/admin/roles/{role_id}/context", headers=headers)
        return ApiAdminRoleContextPayload.model_validate(payload)

    def update_admin_role(
        self,
        role_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/admin/roles/{role_id}/update",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def toggle_admin_role(
        self,
        role_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/roles/{role_id}/toggle", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def delete_admin_role(
        self,
        role_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/roles/{role_id}/delete", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def create_admin_user(
        self,
        schema_id: str | None,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            "/api/v1/admin/users/create",
            headers=headers,
            json_body={"schema_id": schema_id, "form_data": form_data},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def get_admin_users(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminUsersPayload:
        payload = self._get("/api/v1/admin/users", headers=headers)
        return ApiAdminUsersPayload.model_validate(payload)

    def get_admin_user_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminUserCreateContextPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/users/create_context", headers=headers, params=params)
        return ApiAdminUserCreateContextPayload.model_validate(payload)

    def get_admin_user_context(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminUserContextPayload:
        payload = self._get(f"/api/v1/admin/users/{user_id}/context", headers=headers)
        return ApiAdminUserContextPayload.model_validate(payload)

    def update_admin_user(
        self,
        user_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/admin/users/{user_id}/update",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def delete_admin_user(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/users/{user_id}/delete", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def toggle_admin_user(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/users/{user_id}/toggle", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def validate_admin_username(
        self,
        username: str,
        headers: dict[str, str] | None = None,
    ) -> bool:
        payload = self._post(
            "/api/v1/admin/users/validate_username",
            headers=headers,
            json_body={"username": username},
        )
        return bool(payload.get("exists", False))

    def validate_admin_email(
        self,
        email: str,
        headers: dict[str, str] | None = None,
    ) -> bool:
        payload = self._post(
            "/api/v1/admin/users/validate_email",
            headers=headers,
            json_body={"email": email},
        )
        return bool(payload.get("exists", False))

    def authenticate_web_login_internal(
        self,
        username: str,
        password: str,
        headers: dict[str, str] | None = None,
    ) -> ApiAuthLoginPayload:
        payload = self._post(
            "/api/v1/internal/auth/login",
            headers=headers,
            json_body={"username": username, "password": password},
        )
        return ApiAuthLoginPayload.model_validate(payload)

    def get_user_session_internal(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiAuthSessionUserPayload:
        payload = self._get(
            f"/api/v1/internal/users/{user_id}/session",
            headers=headers,
        )
        return ApiAuthSessionUserPayload.model_validate(payload)

    def update_user_last_login_internal(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/internal/users/{user_id}/last_login",
            headers=headers,
        )
        return ApiMutationResultPayload.model_validate(payload)

    def create_admin_asp(
        self,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            "/api/v1/admin/asp/create",
            headers=headers,
            json_body={"config": config},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def get_admin_asp(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminAspPayload:
        payload = self._get("/api/v1/admin/asp", headers=headers)
        return ApiAdminAspPayload.model_validate(payload)

    def get_admin_asp_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminAspCreateContextPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/asp/create_context", headers=headers, params=params)
        return ApiAdminAspCreateContextPayload.model_validate(payload)

    def get_admin_asp_context(
        self,
        assay_panel_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminAspContextPayload:
        payload = self._get(f"/api/v1/admin/asp/{assay_panel_id}/context", headers=headers)
        return ApiAdminAspContextPayload.model_validate(payload)

    def update_admin_asp(
        self,
        assay_panel_id: str,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/admin/asp/{assay_panel_id}/update",
            headers=headers,
            json_body={"config": config},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def toggle_admin_asp(
        self,
        assay_panel_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/asp/{assay_panel_id}/toggle", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def delete_admin_asp(
        self,
        assay_panel_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/asp/{assay_panel_id}/delete", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def create_admin_genelist(
        self,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            "/api/v1/admin/genelists/create",
            headers=headers,
            json_body={"config": config},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def get_admin_genelists(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminGenelistsPayload:
        payload = self._get("/api/v1/admin/genelists", headers=headers)
        return ApiAdminGenelistsPayload.model_validate(payload)

    def get_admin_genelist_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminGenelistCreateContextPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/genelists/create_context", headers=headers, params=params)
        return ApiAdminGenelistCreateContextPayload.model_validate(payload)

    def get_admin_genelist_context(
        self,
        genelist_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminGenelistContextPayload:
        payload = self._get(f"/api/v1/admin/genelists/{genelist_id}/context", headers=headers)
        return ApiAdminGenelistContextPayload.model_validate(payload)

    def get_admin_genelist_view_context(
        self,
        genelist_id: str,
        selected_assay: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminGenelistViewContextPayload:
        params = {"assay": selected_assay} if selected_assay else None
        payload = self._get(
            f"/api/v1/admin/genelists/{genelist_id}/view_context",
            headers=headers,
            params=params,
        )
        return ApiAdminGenelistViewContextPayload.model_validate(payload)

    def update_admin_genelist(
        self,
        genelist_id: str,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/admin/genelists/{genelist_id}/update",
            headers=headers,
            json_body={"config": config},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def toggle_admin_genelist(
        self,
        genelist_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/genelists/{genelist_id}/toggle", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def delete_admin_genelist(
        self,
        genelist_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/genelists/{genelist_id}/delete", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def update_admin_sample(
        self,
        sample_id: str,
        sample: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/admin/samples/{sample_id}/update",
            headers=headers,
            json_body={"sample": sample},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def get_admin_samples(
        self,
        search: str = "",
        headers: dict[str, str] | None = None,
    ) -> ApiAdminSamplesPayload:
        payload = self._get(
            "/api/v1/admin/samples",
            headers=headers,
            params={"search": search} if search else None,
        )
        return ApiAdminSamplesPayload.model_validate(payload)

    def get_admin_sample_context(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminSampleContextPayload:
        payload = self._get(f"/api/v1/admin/samples/{sample_id}/context", headers=headers)
        return ApiAdminSampleContextPayload.model_validate(payload)

    def delete_admin_sample(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/samples/{sample_id}/delete", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def create_admin_aspc(
        self,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            "/api/v1/admin/aspc/create",
            headers=headers,
            json_body={"config": config},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def get_admin_aspc(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminAspcPayload:
        payload = self._get("/api/v1/admin/aspc", headers=headers)
        return ApiAdminAspcPayload.model_validate(payload)

    def get_admin_aspc_create_context(
        self,
        category: str,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminAspcCreateContextPayload:
        params: dict[str, Any] = {"category": category}
        if schema_id:
            params["schema_id"] = schema_id
        payload = self._get("/api/v1/admin/aspc/create_context", headers=headers, params=params)
        return ApiAdminAspcCreateContextPayload.model_validate(payload)

    def get_admin_aspc_context(
        self,
        assay_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiAdminAspcContextPayload:
        payload = self._get(f"/api/v1/admin/aspc/{assay_id}/context", headers=headers)
        return ApiAdminAspcContextPayload.model_validate(payload)

    def update_admin_aspc(
        self,
        assay_id: str,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(
            f"/api/v1/admin/aspc/{assay_id}/update",
            headers=headers,
            json_body={"config": config},
        )
        return ApiMutationResultPayload.model_validate(payload)

    def toggle_admin_aspc(
        self,
        assay_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/aspc/{assay_id}/toggle", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

    def delete_admin_aspc(
        self,
        assay_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/admin/aspc/{assay_id}/delete", headers=headers)
        return ApiMutationResultPayload.model_validate(payload)

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
    ) -> ApiMutationResultPayload:
        payload = self._post(f"/api/v1/coverage/blacklist/{obj_id}/remove", headers=headers)
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


def build_internal_headers() -> dict[str, str]:
    token = current_app.config.get("INTERNAL_API_TOKEN") or current_app.config.get("SECRET_KEY")
    headers = {"X-Requested-With": "XMLHttpRequest"}
    if token:
        headers["X-Coyote-Internal-Token"] = str(token)
    return headers
