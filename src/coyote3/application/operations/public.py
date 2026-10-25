"""Deliberately public, read-only application catalog and reference operations.

This capability exposes only the existing anonymous catalog surface. It cannot
load clinical records, mutate resources or create an authenticated application.
"""

from __future__ import annotations

import csv
import datetime
import io
from collections.abc import Callable, Mapping
from logging import Logger
from typing import TYPE_CHECKING, Any

from coyote3.domain.common.csv_safety import spreadsheet_text
from coyote3.domain.common.errors import api_error

if TYPE_CHECKING:
    from coyote3.application.admin.app_controls import AppControlsService
    from coyote3.application.public.catalog import PublicCatalogService


class PublicApplication:
    """Allowlisted anonymous reads of published catalogs and public reference metadata."""

    def __init__(
        self,
        *,
        catalog: Callable[[], PublicCatalogService],
        controls: Callable[[], AppControlsService],
        config: Mapping[str, Any],
        logger: Logger,
        filter_flags: Callable[[], dict[str, Any]],
        gene_info: Callable[[str], dict[str, Any]],
    ) -> None:
        """Bind public catalog ports and center-owned published metadata.

        Args:
            catalog: Existing read-only published catalog and public reference service.
            controls: Supplies public application-module availability only.
            config: Center configuration; methods select established public keys explicitly.
            logger: Records failures while preserving existing optional metadata behavior.
            filter_flags: Resolves configured public filter flag descriptions.
            gene_info: Resolves public HGNC metadata without clinical cohort information.
        """
        self._catalog, self._controls = catalog, controls
        self._config, self._logger, self._filter_flags = config, logger, filter_flags
        self._gene_info = gene_info

    def gene_info(self, *, gene_id: str) -> dict[str, Any]:
        """Read public reference metadata without requiring a clinical session.

        Args:
            gene_id: Gene identifier or HGNC symbol.

        Returns:
            Existing public gene metadata and normalized identifier context.
        """
        return dict(self._gene_info(gene_id))

    def vep_versions(self) -> dict[str, Any]:
        """List installed VEP reference releases. Public access; no sample data is returned."""
        return dict(self._catalog().vep_reference_versions())

    def vep_reference(self, release: str) -> dict[str, Any]:
        """Read consequence definitions and diagram for an exact installed VEP release.

        Public access. An unavailable release returns 404 rather than newer metadata.

        Args:
            release: Installed major Ensembl release identifier.

        Returns:
            Reference tables, groups, source links and an optional locally stored diagram.
        """
        return dict(self._catalog().vep_reference(release))

    def vep_diagram(self, release: str) -> dict[str, Any]:
        """Return the locally installed Ensembl diagram. Public, read-only access.

        Args:
            release: Exact installed major Ensembl release.

        Returns:
            Image bytes with their MIME type and content digest; 404 if absent.
        """
        diagram = self._catalog().vep_diagram(release)
        return dict(diagram)

    def modules(self) -> dict[str, Any]:
        """Return effective availability for software-defined application modules."""
        return dict(self._controls().public_module_payload())

    def knowledgebase_status(self) -> dict[str, Any]:
        """Build public release metadata without source files or operational paths."""
        try:
            payload = self._catalog().knowledgebase_status()
            releases = list(payload.get("releases") or [])
            installed_sources = {str(item.get("source") or "") for item in releases}
            configured_services = {
                "oncokb_public": self._config.get("ONCOKB_BASE_URL"),
                "clinpgx_public": self._config.get("CLINPGX_BASE_URL"),
            }
            for source, endpoint in configured_services.items():
                if endpoint and source not in installed_sources:
                    releases.append(
                        {
                            "source": source,
                            "release": "Remote service",
                            "status": "configured",
                            "records": 0,
                            "collections": [],
                        }
                    )
            payload["releases"] = sorted(releases, key=lambda item: str(item.get("source") or ""))
            payload["summary"]["configured_services"] = sum(
                (bool(endpoint) for endpoint in configured_services.values())
            )
            payload["summary"]["available_products"] = len(releases)
            return dict(payload)
        except Exception as exc:
            self._logger.warning("Could not build knowledgebase status: %s", exc)
            return {"releases": [], "summary": {"installed_products": 0, "total_records": 0}}

    def software_versions(self) -> dict[str, Any]:
        """Return software versions observed in stored sample metadata."""
        try:
            return dict(self._catalog().observed_software_versions())
        except Exception as exc:
            self._logger.warning("Could not build public software versions: %s", exc)
            return {"pipelines": {}}

    def reference_versions(self) -> dict[str, Any]:
        """Return reference database versions observed in samples and VEP metadata."""
        try:
            return dict(self._catalog().observed_reference_versions())
        except Exception as exc:
            self._logger.warning("Could not build public reference versions: %s", exc)
            return {"sample_database_versions": {}, "vep_metadata": []}

    def filter_flag_metadata(self) -> dict[str, Any]:
        """Return center-configurable VCF filter flag metadata."""
        return dict(self._filter_flags())

    def genelist_view_context(self, genelist_id: str, assay: str | None = None) -> dict[str, Any]:
        """Return public view context for a genelist.


        Args:
            genelist_id: Genelist identifier to inspect.
            assay: Optional assay used to scope visible genes.

        Returns:
            dict: Public genelist view payload.
        """
        service = self._catalog()
        payload = service.genelist_view_context(genelist_id, assay)
        if not payload:
            raise api_error(404, "Genelist not found")
        return dict(payload)

    def asp_genes(self, asp_id: str) -> dict[str, Any]:
        """Return public genes for an assay panel.


        Args:
            asp_id: Assay-panel identifier to inspect.

        Returns:
            dict: Public assay-panel gene payload.
        """
        service = self._catalog()
        return dict(service.asp_genes_payload(asp_id))

    def assay_catalog_isgl_genes_view(self, isgl_key: str) -> dict[str, Any]:
        """Return public catalog genes for a catalog genelist.


        Args:
            isgl_key: Catalog genelist identifier to inspect.

        Returns:
            dict: Public gene-symbol payload.
        """
        service = self._catalog()
        return dict(service.assay_catalog_gene_symbols_payload(isgl_key))

    def assay_catalog_matrix_context(
        self, page: int = 1, per_page: int = 100, gene: str | None = None
    ) -> dict[str, Any]:
        """Return the public assay-catalog matrix payload.

        Returns:
            dict: Assay-catalog matrix payload.
        """
        service = self._catalog()
        vm = service.published_matrix(page=page, per_page=per_page, gene=gene)
        return dict(vm)

    def catalog_offerings(self) -> dict[str, Any]:
        """Browse reviewed service offerings, prices and effective gene scopes."""
        return dict(self._catalog().published_offerings())

    def assay_catalog_context(
        self, mod: str | None = None, cat: str | None = None, isgl_key: str | None = None
    ) -> dict[str, Any]:
        """Return public assay-catalog context for the selected modality/category."""
        return dict(self._catalog().published_context(mod, cat, isgl_key))

    def assay_catalog_genes_csv_context(
        self, mod: str, cat: str | None = None, isgl_key: str | None = None
    ) -> dict[str, Any]:
        """Return a CSV export payload for public assay-catalog genes."""
        service = self._catalog()
        context = service.published_context(mod, cat, isgl_key)
        selected_mod = mod
        mode, rows = (context["gene_mode"], context["genes"])
        sio = io.StringIO()
        writer = csv.writer(sio, lineterminator="\n")
        writer.writerow(
            ["HGNC_ID", "Gene_Symbol", "Chromosome", "Start", "End", "Gene_Type", "Drug Target"]
        )
        for gene in rows:
            writer.writerow(
                [
                    spreadsheet_text(value)
                    for value in [
                        gene.get("hgnc_id") or "",
                        gene.get("hgnc_symbol") or gene.get("symbol") or "",
                        gene.get("chromosome") or "",
                        gene.get("start"),
                        gene.get("end"),
                        ",".join(gene.get("gene_type") or []),
                        gene.get("drug_target") or "",
                    ]
                ]
            )
        dt = datetime.date.today().isoformat()
        if not cat:
            label = f"{selected_mod}.{(mode if not isgl_key else f'isgl-{isgl_key}')}"
        else:
            label = f"{selected_mod}.{cat}.{(mode if not isgl_key else f'isgl-{isgl_key}')}"
        fname = f"{label}.{dt}.genes.csv"
        return {"filename": fname, "content": sio.getvalue()}
