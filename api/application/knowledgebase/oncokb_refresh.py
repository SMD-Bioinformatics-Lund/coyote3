"""Explicit, HGNC-backed refresh workflow for public OncoKB reference data."""

from __future__ import annotations

from typing import Any

from api.application.ingest.oncokb_public import refresh_public_oncokb_gene_cache
from api.infra.knowledgebase.public_oncokb import PublicOncoKbClient


class PublicOncoKbRefreshService:
    """Refresh shared public OncoKB gene collections from the HGNC catalogue."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        config: dict[str, Any],
        audit_service: Any | None = None,
    ) -> "PublicOncoKbRefreshService":
        """Build the service from the initialized application store."""
        return cls(
            cache_repository=store.oncokb_public_cache_repository,
            hgnc_repository=store.hgnc_repository,
            config=config,
            audit_service=audit_service,
        )

    def __init__(
        self,
        *,
        cache_repository: Any,
        hgnc_repository: Any,
        config: dict[str, Any],
        audit_service: Any | None = None,
    ) -> None:
        self.cache_repository = cache_repository
        self.hgnc_repository = hgnc_repository
        self.config = config
        self.audit_service = audit_service

    def refresh(self) -> dict[str, int | str]:
        """Fetch the public OncoKB catalogues once and upsert HGNC-matched records."""
        if not bool(self.config.get("ONCOKB_PUBLIC_LOOKUPS_ENABLED", True)):
            return {"status": "disabled"}

        client = PublicOncoKbClient(
            base_url=str(
                self.config.get("ONCOKB_BASE_URL") or "https://public.api.oncokb.org/api/v1"
            ),
            timeout=float(self.config.get("ONCOKB_REQUEST_TIMEOUT_SECONDS", 3.0) or 3.0),
        )
        try:
            result = refresh_public_oncokb_gene_cache(
                client=client,
                cache_repository=self.cache_repository,
                hgnc_repository=self.hgnc_repository,
            )
        except Exception as exc:
            if self.audit_service is not None:
                self.audit_service.record(
                    "knowledgebase.oncokb_public.refresh.failed",
                    "Public OncoKB reference refresh failed",
                    severity="error",
                    category="operations",
                    outcome="failure",
                    resource_type="knowledgebase",
                    resource_id="oncokb_public",
                    tags=["knowledgebase", "oncokb", "refresh"],
                    metadata={"error_type": type(exc).__name__},
                )
            raise

        payload: dict[str, int | str] = {"status": "ok", **result}
        if self.audit_service is not None:
            self.audit_service.record(
                "knowledgebase.oncokb_public.refresh.completed",
                "Public OncoKB reference refresh completed",
                category="operations",
                outcome="success",
                resource_type="knowledgebase",
                resource_id="oncokb_public",
                tags=["knowledgebase", "oncokb", "refresh"],
                metadata={
                    "hgnc_gene_records": result["hgnc_gene_records"],
                    "cancer_genes_upserted": result["cancer_genes_upserted"],
                    "cancer_genes_removed": result["cancer_genes_removed"],
                    "curated_genes_upserted": result["curated_genes_upserted"],
                    "curated_genes_removed": result["curated_genes_removed"],
                },
            )
        return payload
