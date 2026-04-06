"""Coverage workflow service."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from api.http import api_error
from api.services.coverage.processing import CoverageProcessingService


class CoverageService:
    """Own coverage read and blacklist-view workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "CoverageService":
        """Build the service from the shared store."""
        return cls(
            assay_configuration_handler=store.assay_configuration_handler,
            assay_panel_handler=store.assay_panel_handler,
            gene_list_handler=store.gene_list_handler,
            coverage_handler=store.coverage_handler,
            grouped_coverage_handler=store.grouped_coverage_handler,
        )

    def __init__(
        self,
        *,
        assay_configuration_handler: Any,
        assay_panel_handler: Any,
        gene_list_handler: Any,
        coverage_handler: Any,
        grouped_coverage_handler: Any,
    ) -> None:
        """Create the service with explicit injected handlers."""
        self.assay_configuration_handler = assay_configuration_handler
        self.assay_panel_handler = assay_panel_handler
        self.gene_list_handler = gene_list_handler
        self.coverage_handler = coverage_handler
        self.grouped_coverage_handler = grouped_coverage_handler

    def sample_payload(
        self, *, sample: dict, cov_cutoff: int, effective_genes_resolver
    ) -> dict[str, Any]:
        """Return coverage data for a sample.

        Args:
            sample: Sample payload to inspect.
            cov_cutoff: Coverage threshold for low-coverage detection.
            effective_genes_resolver: Helper used to resolve effective genes.

        Returns:
            dict[str, Any]: Coverage payload for charts and tables.
        """
        sample_assay = sample.get("assay", "unknown")
        sample_profile = sample.get("profile", "production")
        assay_config = self.assay_configuration_handler.get_aspc_no_meta(
            sample_assay, sample_profile
        )
        if not assay_config:
            raise api_error(404, "Assay config not found")

        assay_group = assay_config.get("assay_group", "unknown")
        assay_panel_doc = self.assay_panel_handler.get_asp(asp_name=sample_assay)
        sample_filters = sample.get("filters", {})
        checked_genelists = sample_filters.get("genelists", [])

        if checked_genelists:
            checked_genelists_genes_dict = self.gene_list_handler.get_isgl_by_ids(checked_genelists)
            _genes_covered_in_panel, filter_genes = effective_genes_resolver(
                sample,
                assay_panel_doc,
                checked_genelists_genes_dict,
            )
        else:
            asp_id = assay_panel_doc.get("asp_id")
            if not asp_id:
                raise api_error(500, "ASP is missing required asp_id")
            checked_genelists = [asp_id]
            filter_genes = assay_panel_doc.get("covered_genes", [])

        cov_dict = self.coverage_handler.get_sample_coverage(str(sample["_id"])) or {}
        cov_dict = deepcopy(cov_dict)
        cov_dict.pop("_id", None)
        sample_payload = deepcopy(sample)
        sample_payload.pop("_id", None)

        filtered_dict = CoverageProcessingService.filter_genes_from_form(
            cov_dict,
            filter_genes,
            assay_group,
            grouped_coverage_handler=self.grouped_coverage_handler,
        )
        filtered_dict = CoverageProcessingService.find_low_covered_genes(
            filtered_dict,
            cov_cutoff,
            assay_group,
            grouped_coverage_handler=self.grouped_coverage_handler,
        )
        cov_table = CoverageProcessingService.coverage_table(filtered_dict, cov_cutoff)
        filtered_dict = CoverageProcessingService.organize_data_for_d3(filtered_dict)

        return {
            "coverage": filtered_dict,
            "cov_cutoff": cov_cutoff,
            "sample": sample_payload,
            "genelists": checked_genelists,
            "smp_grp": assay_group,
            "cov_table": cov_table,
        }

    def blacklisted_payload(self, *, group: str, user) -> dict[str, Any]:
        """Return blacklisted coverage regions for an assay group.

        Args:
            group: Assay group to inspect.
            user: Authenticated user requesting the data.

        Returns:
            dict[str, Any]: Grouped blacklist payload.
        """
        if group not in set(user.assay_groups or []):
            raise api_error(403, "Access denied: You do not belong to the target assay.")

        grouped_by_gene = defaultdict(dict)
        blacklisted = list(self.grouped_coverage_handler.get_regions_per_group(group) or [])
        for entry in blacklisted:
            if entry["region"] == "gene":
                grouped_by_gene[entry["gene"]]["gene"] = entry["_id"]
            elif entry["region"] == "CDS":
                grouped_by_gene[entry["gene"]]["CDS"] = entry
            elif entry["region"] == "probe":
                grouped_by_gene[entry["gene"]]["probe"] = entry

        return {"blacklisted": grouped_by_gene, "group": group}
