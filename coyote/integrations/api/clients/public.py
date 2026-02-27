"""Public API client mixin methods."""

from __future__ import annotations

from typing import Any

from coyote.integrations.api.base import ApiPayload


class PublicApiClientMixin:
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

