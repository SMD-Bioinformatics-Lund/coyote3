"""Coverage workflow service."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from api.core.coverage.coverage_processing import CoverageProcessingService
from api.http import api_error
from api.repositories.coverage_repository import (
    CoverageRepository as MongoCoverageRepository,
    CoverageRouteRepository as MongoCoverageRouteRepository,
)


class CoverageService:
    """Own coverage read and blacklist-view workflows."""

    def __init__(self, repository=None, processing_repository=None) -> None:
        """Handle __init__.

        Args:
                repository: Repository. Optional argument.
                processing_repository: Processing repository. Optional argument.
        """
        self.repository = repository or MongoCoverageRouteRepository()
        self.processing_repository = processing_repository or MongoCoverageRepository()
        if not CoverageProcessingService.has_repository():
            CoverageProcessingService.set_repository(self.processing_repository)

    def sample_payload(self, *, sample: dict, cov_cutoff: int, effective_genes_resolver) -> dict[str, Any]:
        """Handle sample payload.

        Args:
            sample (dict): Value for ``sample``.
            cov_cutoff (int): Value for ``cov_cutoff``.
            effective_genes_resolver: Value for ``effective_genes_resolver``.

        Returns:
            dict[str, Any]: The function result.
        """
        sample_assay = sample.get("assay", "unknown")
        sample_profile = sample.get("profile", "production")
        assay_config = self.repository.get_aspc_no_meta(sample_assay, sample_profile)
        if not assay_config:
            raise api_error(404, "Assay config not found")

        assay_group = assay_config.get("assay_group", "unknown")
        assay_panel_doc = self.repository.get_asp(asp_name=sample_assay)
        sample_filters = sample.get("filters", {})
        checked_genelists = sample_filters.get("genelists", [])

        if checked_genelists:
            checked_genelists_genes_dict = self.repository.get_isgl_by_ids(checked_genelists)
            _genes_covered_in_panel, filter_genes = effective_genes_resolver(
                sample,
                assay_panel_doc,
                checked_genelists_genes_dict,
            )
        else:
            checked_genelists = [assay_panel_doc.get("_id")]
            filter_genes = assay_panel_doc.get("covered_genes", [])

        cov_dict = self.repository.get_sample_coverage(str(sample["_id"])) or {}
        cov_dict = deepcopy(cov_dict)
        cov_dict.pop("_id", None)
        sample_payload = deepcopy(sample)
        sample_payload.pop("_id", None)

        filtered_dict = CoverageProcessingService.filter_genes_from_form(cov_dict, filter_genes, assay_group)
        filtered_dict = CoverageProcessingService.find_low_covered_genes(filtered_dict, cov_cutoff, assay_group)
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
        """Handle blacklisted payload.

        Args:
            group (str): Value for ``group``.
            user: Value for ``user``.

        Returns:
            dict[str, Any]: The function result.
        """
        if group not in set(user.assay_groups or []):
            raise api_error(403, "Access denied: You do not belong to the target assay.")

        grouped_by_gene = defaultdict(dict)
        blacklisted = self.repository.get_regions_per_group(group)
        for entry in blacklisted:
            if entry["region"] == "gene":
                grouped_by_gene[entry["gene"]]["gene"] = entry["_id"]
            elif entry["region"] == "CDS":
                grouped_by_gene[entry["gene"]]["CDS"] = entry
            elif entry["region"] == "probe":
                grouped_by_gene[entry["gene"]]["probe"] = entry

        return {"blacklisted": grouped_by_gene, "group": group}
