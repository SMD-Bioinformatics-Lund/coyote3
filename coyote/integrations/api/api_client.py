"""Server-side API client used by Flask web routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx
from flask import current_app


@dataclass
class ApiRequestError(Exception):
    message: str
    status_code: int | None = None
    payload: Any | None = None

    def __str__(self) -> str:
        return self.message


class ApiPayload(dict[str, Any]):
    """Dict with attribute access for API payloads."""

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value

    def model_dump(self) -> dict[str, Any]:
        return _to_builtin(self)



def _as_api_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return ApiPayload({k: _as_api_payload(v) for k, v in value.items()})
    if isinstance(value, list):
        return [_as_api_payload(v) for v in value]
    return value


def _to_builtin(value: Any) -> Any:
    if isinstance(value, ApiPayload):
        return {k: _to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_builtin(v) for v in value]
    return value


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
    ) -> ApiPayload:
        return _as_api_payload(self._request("GET", path, headers=headers, params=params))

    def _post(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        return _as_api_payload(self._request("POST", path, headers=headers, params=params, json_body=json_body))

    def get_json(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> ApiPayload:
        return self._get(path, headers=headers, params=params)

    def post_json(
        self,
        path: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> ApiPayload:
        return self._post(path, headers=headers, params=params, json_body=json_body)

    def get_rna_fusions(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/rna/samples/{sample_id}/fusions", headers=headers)
        return payload

    def get_dashboard_summary(
        self, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get("/api/v1/dashboard/summary", headers=headers)
        return payload

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

    def get_public_genelist_view_context(
        self,
        genelist_id: str,
        selected_assay: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"assay": selected_assay} if selected_assay else None
        payload = self._get(
            f"/api/v1/public/genelists/{genelist_id}/view_context",
            headers=headers,
            params=params,
        )
        return payload

    def get_public_asp_genes(
        self,
        asp_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/public/asp/{asp_id}/genes", headers=headers)
        return payload

    def get_public_assay_catalog_genes_view(
        self,
        isgl_key: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/public/assay-catalog/genes/{isgl_key}/view_context",
            headers=headers,
        )
        return payload

    def get_public_assay_catalog_matrix_context(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/public/assay-catalog-matrix/context", headers=headers)
        return payload

    def get_public_assay_catalog_context(
        self,
        mod: str | None = None,
        cat: str | None = None,
        isgl_key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params: dict[str, Any] = {}
        if mod is not None:
            params["mod"] = mod
        if cat is not None:
            params["cat"] = cat
        if isgl_key is not None:
            params["isgl_key"] = isgl_key
        payload = self._get("/api/v1/public/assay-catalog/context", headers=headers, params=params)
        return payload

    def get_public_assay_catalog_genes_csv_context(
        self,
        mod: str,
        cat: str | None = None,
        isgl_key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params: dict[str, Any] = {"mod": mod}
        if cat is not None:
            params["cat"] = cat
        if isgl_key is not None:
            params["isgl_key"] = isgl_key
        payload = self._get("/api/v1/public/assay-catalog/genes.csv/context", headers=headers, params=params)
        return payload

    def get_dna_variants(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/dna/samples/{sample_id}/variants", headers=headers)
        return payload

    def get_dna_plot_context(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/dna/samples/{sample_id}/plot_context", headers=headers)
        return payload

    def get_rna_fusion(
        self, sample_id: str, fusion_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/rna/samples/{sample_id}/fusions/{fusion_id}",
            headers=headers,
        )
        return payload

    def get_dna_variant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}",
            headers=headers,
        )
        return payload

    def get_dna_cnv(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}",
            headers=headers,
        )
        return payload

    def get_dna_translocation(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}",
            headers=headers,
        )
        return payload

    def get_dna_cnvs(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/cnvs",
            headers=headers,
        )
        return payload

    def get_dna_translocations(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/translocations",
            headers=headers,
        )
        return payload

    def get_dna_biomarkers(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/biomarkers",
            headers=headers,
        )
        return payload

    def get_dna_report_preview(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._get(
            f"/api/v1/dna/samples/{sample_id}/report/preview",
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

    def save_dna_report(
        self, sample_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/report/save",
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

    def mark_dna_cnv_interesting(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/interesting", headers=headers)
        return payload

    def unmark_dna_cnv_interesting(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unmarkinteresting",
            headers=headers,
        )
        return payload

    def mark_dna_cnv_false_positive(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/fpcnv", headers=headers)
        return payload

    def unmark_dna_cnv_false_positive(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/unfpcnv", headers=headers)
        return payload

    def mark_dna_cnv_noteworthy(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/noteworthycnv",
            headers=headers,
        )
        return payload

    def unmark_dna_cnv_noteworthy(
        self, sample_id: str, cnv_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/notnoteworthycnv",
            headers=headers,
        )
        return payload

    def hide_dna_cnv_comment(
        self, sample_id: str, cnv_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return payload

    def unhide_dna_cnv_comment(
        self, sample_id: str, cnv_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return payload

    def mark_dna_translocation_interesting(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/interestingtransloc",
            headers=headers,
        )
        return payload

    def unmark_dna_translocation_interesting(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/uninterestingtransloc",
            headers=headers,
        )
        return payload

    def mark_dna_translocation_false_positive(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/fptransloc",
            headers=headers,
        )
        return payload

    def unmark_dna_translocation_false_positive(
        self, sample_id: str, transloc_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/ptransloc",
            headers=headers,
        )
        return payload

    def hide_dna_translocation_comment(
        self, sample_id: str, transloc_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return payload

    def unhide_dna_translocation_comment(
        self, sample_id: str, transloc_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return payload

    def mark_dna_variant_false_positive(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/fp", headers=headers)
        return payload

    def unmark_dna_variant_false_positive(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/unfp", headers=headers)
        return payload

    def mark_dna_variant_interesting(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/interest", headers=headers)
        return payload

    def unmark_dna_variant_interesting(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/uninterest",
            headers=headers,
        )
        return payload

    def mark_dna_variant_irrelevant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/irrelevant",
            headers=headers,
        )
        return payload

    def unmark_dna_variant_irrelevant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/relevant",
            headers=headers,
        )
        return payload

    def blacklist_dna_variant(
        self, sample_id: str, var_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/blacklist", headers=headers)
        return payload

    def hide_dna_variant_comment(
        self, sample_id: str, var_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/hide",
            headers=headers,
        )
        return payload

    def unhide_dna_variant_comment(
        self, sample_id: str, var_id: str, comment_id: str, headers: dict[str, str] | None = None
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/{var_id}/comments/{comment_id}/unhide",
            headers=headers,
        )
        return payload

    def set_dna_variants_false_positive_bulk(
        self,
        sample_id: str,
        variant_ids: list[str],
        apply: bool,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/bulk/fp",
            headers=headers,
            params={"apply": str(bool(apply)).lower(), "variant_ids": variant_ids},
        )
        return payload

    def set_dna_variants_irrelevant_bulk(
        self,
        sample_id: str,
        variant_ids: list[str],
        apply: bool,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/bulk/irrelevant",
            headers=headers,
            params={"apply": str(bool(apply)).lower(), "variant_ids": variant_ids},
        )
        return payload

    def set_dna_variants_tier_bulk(
        self,
        sample_id: str,
        variant_ids: list[str],
        assay_group: str | None,
        subpanel: str | None,
        tier: str | int | None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/bulk/tier",
            headers=headers,
            json_body={
                "variant_ids": variant_ids,
                "assay_group": assay_group,
                "subpanel": subpanel,
                "tier": tier,
            },
        )
        return payload

    def classify_dna_variant(
        self,
        sample_id: str,
        target_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/classify",
            headers=headers,
            json_body={"id": target_id, "form_data": form_data},
        )
        return payload

    def remove_dna_variant_classification(
        self,
        sample_id: str,
        target_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/variants/rmclassify",
            headers=headers,
            json_body={"id": target_id, "form_data": form_data},
        )
        return payload

    def add_dna_variant_comment(
        self,
        sample_id: str,
        target_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/dna/samples/{sample_id}/comments/add",
            headers=headers,
            json_body={"id": target_id, "form_data": form_data},
        )
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

    def create_admin_permission(
        self,
        schema_id: str | None,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/permissions/create",
            headers=headers,
            json_body={"schema_id": schema_id, "form_data": form_data},
        )
        return payload

    def get_admin_permissions(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/permissions", headers=headers)
        return payload

    def get_admin_permission_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/permissions/create_context", headers=headers, params=params)
        return payload

    def get_admin_permission_context(
        self,
        perm_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/permissions/{perm_id}/context", headers=headers)
        return payload

    def update_admin_permission(
        self,
        perm_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/permissions/{perm_id}/update",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return payload

    def toggle_admin_permission(
        self,
        perm_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/permissions/{perm_id}/toggle", headers=headers)
        return payload

    def delete_admin_permission(
        self,
        perm_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/permissions/{perm_id}/delete", headers=headers)
        return payload

    def create_admin_schema(
        self,
        schema_doc: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/schemas/create",
            headers=headers,
            json_body={"schema": schema_doc},
        )
        return payload

    def get_admin_schemas(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/schemas", headers=headers)
        return payload

    def get_admin_schema_context(
        self,
        schema_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/schemas/{schema_id}/context", headers=headers)
        return payload

    def update_admin_schema(
        self,
        schema_id: str,
        schema_doc: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/schemas/{schema_id}/update",
            headers=headers,
            json_body={"schema": schema_doc},
        )
        return payload

    def toggle_admin_schema(
        self,
        schema_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/schemas/{schema_id}/toggle", headers=headers)
        return payload

    def delete_admin_schema(
        self,
        schema_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/schemas/{schema_id}/delete", headers=headers)
        return payload

    def create_admin_role(
        self,
        schema_id: str | None,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/roles/create",
            headers=headers,
            json_body={"schema_id": schema_id, "form_data": form_data},
        )
        return payload

    def get_admin_roles(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/roles", headers=headers)
        return payload

    def get_admin_role_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/roles/create_context", headers=headers, params=params)
        return payload

    def get_admin_role_context(
        self,
        role_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/roles/{role_id}/context", headers=headers)
        return payload

    def update_admin_role(
        self,
        role_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/roles/{role_id}/update",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return payload

    def toggle_admin_role(
        self,
        role_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/roles/{role_id}/toggle", headers=headers)
        return payload

    def delete_admin_role(
        self,
        role_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/roles/{role_id}/delete", headers=headers)
        return payload

    def create_admin_user(
        self,
        schema_id: str | None,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/users/create",
            headers=headers,
            json_body={"schema_id": schema_id, "form_data": form_data},
        )
        return payload

    def get_admin_users(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/users", headers=headers)
        return payload

    def get_admin_user_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/users/create_context", headers=headers, params=params)
        return payload

    def get_admin_user_context(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/users/{user_id}/context", headers=headers)
        return payload

    def update_admin_user(
        self,
        user_id: str,
        form_data: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/users/{user_id}/update",
            headers=headers,
            json_body={"form_data": form_data},
        )
        return payload

    def delete_admin_user(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/users/{user_id}/delete", headers=headers)
        return payload

    def toggle_admin_user(
        self,
        user_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/users/{user_id}/toggle", headers=headers)
        return payload

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

    def create_admin_asp(
        self,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/asp/create",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def get_admin_asp(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/asp", headers=headers)
        return payload

    def get_admin_asp_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/asp/create_context", headers=headers, params=params)
        return payload

    def get_admin_asp_context(
        self,
        assay_panel_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/asp/{assay_panel_id}/context", headers=headers)
        return payload

    def update_admin_asp(
        self,
        assay_panel_id: str,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/asp/{assay_panel_id}/update",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def toggle_admin_asp(
        self,
        assay_panel_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/asp/{assay_panel_id}/toggle", headers=headers)
        return payload

    def delete_admin_asp(
        self,
        assay_panel_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/asp/{assay_panel_id}/delete", headers=headers)
        return payload

    def create_admin_genelist(
        self,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/genelists/create",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def get_admin_genelists(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/genelists", headers=headers)
        return payload

    def get_admin_genelist_create_context(
        self,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"schema_id": schema_id} if schema_id else None
        payload = self._get("/api/v1/admin/genelists/create_context", headers=headers, params=params)
        return payload

    def get_admin_genelist_context(
        self,
        genelist_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/genelists/{genelist_id}/context", headers=headers)
        return payload

    def get_admin_genelist_view_context(
        self,
        genelist_id: str,
        selected_assay: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params = {"assay": selected_assay} if selected_assay else None
        payload = self._get(
            f"/api/v1/admin/genelists/{genelist_id}/view_context",
            headers=headers,
            params=params,
        )
        return payload

    def update_admin_genelist(
        self,
        genelist_id: str,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/genelists/{genelist_id}/update",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def toggle_admin_genelist(
        self,
        genelist_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/genelists/{genelist_id}/toggle", headers=headers)
        return payload

    def delete_admin_genelist(
        self,
        genelist_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/genelists/{genelist_id}/delete", headers=headers)
        return payload

    def update_admin_sample(
        self,
        sample_id: str,
        sample: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/samples/{sample_id}/update",
            headers=headers,
            json_body={"sample": sample},
        )
        return payload

    def get_admin_samples(
        self,
        search: str = "",
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(
            "/api/v1/admin/samples",
            headers=headers,
            params={"search": search} if search else None,
        )
        return payload

    def get_admin_sample_context(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/samples/{sample_id}/context", headers=headers)
        return payload

    def delete_admin_sample(
        self,
        sample_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/samples/{sample_id}/delete", headers=headers)
        return payload

    def create_admin_aspc(
        self,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            "/api/v1/admin/aspc/create",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def get_admin_aspc(
        self,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get("/api/v1/admin/aspc", headers=headers)
        return payload

    def get_admin_aspc_create_context(
        self,
        category: str,
        schema_id: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        params: dict[str, Any] = {"category": category}
        if schema_id:
            params["schema_id"] = schema_id
        payload = self._get("/api/v1/admin/aspc/create_context", headers=headers, params=params)
        return payload

    def get_admin_aspc_context(
        self,
        assay_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._get(f"/api/v1/admin/aspc/{assay_id}/context", headers=headers)
        return payload

    def update_admin_aspc(
        self,
        assay_id: str,
        config: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(
            f"/api/v1/admin/aspc/{assay_id}/update",
            headers=headers,
            json_body={"config": config},
        )
        return payload

    def toggle_admin_aspc(
        self,
        assay_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/aspc/{assay_id}/toggle", headers=headers)
        return payload

    def delete_admin_aspc(
        self,
        assay_id: str,
        headers: dict[str, str] | None = None,
    ) -> ApiPayload:
        payload = self._post(f"/api/v1/admin/aspc/{assay_id}/delete", headers=headers)
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
