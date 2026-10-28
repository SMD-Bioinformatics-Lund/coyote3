"""Public assay catalog application service used by FastAPI public routes."""

from __future__ import annotations

from typing import Any

from coyote3.application.public.catalog_gene_views import PublicCatalogGeneViewsMixin
from coyote3.application.public.published_catalog_views import (
    publication_context,
    publication_matrix,
)
from coyote3.contracts.schemas.catalog_offerings import CatalogDiscoveryDoc
from coyote3.domain.common.errors import api_error


class PublicCatalogService(PublicCatalogGeneViewsMixin):
    """Provide public catalog workflows."""

    def _load_catalog_document(self) -> dict[str, Any]:
        """Read the stored current publication; return an empty document before publication."""
        if self.public_assay_catalog_repository is None:
            return {}
        return self.public_assay_catalog_repository.get_default() or {}

    def published_context(
        self, mod: str | None = None, cat: str | None = None, isgl_key: str | None = None
    ) -> dict:
        """Return navigation and gene rows from the current approved publication.

        Args:
            mod: Optional molecular modality filter.
            cat: Optional published offering identifier.
            isgl_key: Optional public list identifier within the selected offerings.

        Returns:
            Frozen navigation, service details and effective gene rows.

        Raises:
            AppError: The requested context is not published.
        """
        return publication_context(self.published_offerings(), mod, cat, isgl_key)

    def published_matrix(
        self, *, page: int = 1, per_page: int = 100, gene: str | None = None
    ) -> dict:
        """Return a paginated comparison of approved effective gene scopes.

        Args:
            page: One-based result page.
            per_page: Maximum number of gene rows in the page.
            gene: Optional case-insensitive gene substring.

        Returns:
            Published scopes with presence cells, current knowledgebase membership
            for the visible genes, and pagination metadata.
        """
        matrix = publication_matrix(
            self.published_offerings(), page=page, per_page=per_page, gene=gene
        )
        matrix["gene_markers"] = self.knowledgebase_gene_markers(matrix["genes"])
        return matrix

    def published_offerings(self) -> dict:
        """Return only reviewed publication snapshots without consulting live resources."""
        document = self._load_catalog_document()
        return CatalogDiscoveryDoc(
            version=document.get("version", 0),
            header=document.get("header") or "Genomic test catalog",
            description=document.get("description") or "",
            offerings=document.get("published_offerings") or [],
        ).model_dump(mode="json")

    @classmethod
    def from_store(cls, store: Any) -> "PublicCatalogService":
        """Build the service from the runtime store."""
        return cls(
            assay_panel_repository=store.assay_panel_repository,
            hgnc_repository=store.hgnc_repository,
            gene_list_repository=store.gene_list_repository,
            sample_repository=store.sample_repository,
            vep_metadata_repository=store.vep_metadata_repository,
            knowledgebase_version_repository=getattr(
                store, "knowledgebase_version_repository", None
            ),
            oncokb_public_cache_repository=getattr(store, "oncokb_public_cache_repository", None),
            clinpgx_public_repository=getattr(store, "clinpgx_public_repository", None),
            civic_repository=getattr(store, "civic_repository", None),
            cosmic_repository=getattr(store, "cosmic_repository", None),
            public_assay_catalog_repository=store.public_assay_catalog_repository,
        )

    def __init__(
        self,
        *,
        assay_panel_repository: Any,
        hgnc_repository: Any,
        gene_list_repository: Any,
        sample_repository: Any,
        vep_metadata_repository: Any,
        knowledgebase_version_repository: Any | None = None,
        oncokb_public_cache_repository: Any | None = None,
        clinpgx_public_repository: Any | None = None,
        civic_repository: Any | None = None,
        cosmic_repository: Any | None = None,
        public_assay_catalog_repository: Any | None = None,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.assay_panel_repository = assay_panel_repository
        self.hgnc_repository = hgnc_repository
        self.gene_list_repository = gene_list_repository
        self.sample_repository = sample_repository
        self.vep_metadata_repository = vep_metadata_repository
        self.knowledgebase_version_repository = knowledgebase_version_repository
        self.oncokb_public_cache_repository = oncokb_public_cache_repository
        self.clinpgx_public_repository = clinpgx_public_repository
        self.civic_repository = civic_repository
        self.cosmic_repository = cosmic_repository
        self.public_assay_catalog_repository = public_assay_catalog_repository

    def knowledgebase_status(self) -> dict[str, Any]:
        """Return non-sensitive installed knowledgebase release metadata."""
        releases = (
            self.knowledgebase_version_repository.list_active_releases()
            if self.knowledgebase_version_repository is not None
            else []
        )
        return {
            "releases": releases,
            "summary": {
                "installed_products": len(releases),
                "total_records": sum(int(item.get("records") or 0) for item in releases),
            },
        }

    def observed_software_versions(self) -> dict[str, object]:
        """Return bounded software versions observed across ready samples."""
        observed = self.sample_repository.get_observed_software_versions()
        return {"pipelines": observed.get("pipelines") or {}}

    def observed_reference_versions(self) -> dict[str, object]:
        """Return observed sample and configured VEP metadata versions."""
        return {
            "sample_database_versions": self.sample_repository.get_observed_database_versions(),
            "vep_metadata": self.vep_metadata_repository.list_versions(),
        }

    def vep_reference_versions(self) -> dict:
        """Return installed numeric major releases without reading sample data.

        Returns:
            Major-release identifiers sorted newest first.
        """
        versions = self.vep_metadata_repository.list_versions()
        return {"versions": sorted((v for v in versions if v.isdecimal()), key=int, reverse=True)}

    def vep_reference(self, release: str) -> dict:
        """Return one installed public VEP reference without substituting another release.

        Args:
            release: Major release selected by the caller.

        Returns:
            Public reference definitions, provenance and an optional stored diagram.

        Raises:
            APIError: The selected release is not installed.
        """
        document = self.vep_metadata_repository.get_public_reference(release)
        if not document:
            raise api_error(404, "VEP reference release is not installed")
        return document

    def vep_diagram(self, release: str) -> dict:
        """Return a release's binary diagram independently of its reference tables.

        Args:
            release: Exact installed major release.

        Returns:
            Original image bytes, MIME type and content digest.

        Raises:
            APIError: No diagram is installed for this release.
        """
        diagram = self.vep_metadata_repository.get_diagram(release)
        if not diagram:
            raise api_error(404, "VEP diagram is not installed")
        return diagram
