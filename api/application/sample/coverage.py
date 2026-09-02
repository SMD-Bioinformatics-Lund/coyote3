"""Coverage workflow service."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from api.application.common.assay_config import get_formatted_assay_config
from api.application.coverage.processing import CoverageProcessingService
from api.domain.common.errors import forbidden_error, setup_error


class CoverageService:
    """Own coverage read and blacklist-view workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "CoverageService":
        """Build the service from the runtime store."""
        return cls(
            assay_configuration_repository=store.assay_configuration_repository,
            assay_panel_repository=store.assay_panel_repository,
            coverage_repository=store.coverage_repository,
            grouped_coverage_repository=store.grouped_coverage_repository,
        )

    def __init__(
        self,
        *,
        assay_configuration_repository: Any,
        assay_panel_repository: Any,
        coverage_repository: Any,
        grouped_coverage_repository: Any,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.assay_configuration_repository = assay_configuration_repository
        self.assay_panel_repository = assay_panel_repository
        self.coverage_repository = coverage_repository
        self.grouped_coverage_repository = grouped_coverage_repository

    def sample_payload(self, *, sample: dict, cov_cutoff: int) -> dict[str, Any]:
        """Return coverage data for a sample.

        Args:
            sample: Sample payload to inspect.
            cov_cutoff: Coverage threshold for low-coverage detection.
        Returns:
            dict[str, Any]: Coverage payload for charts and tables.
        """
        sample_assay = sample.get("asp_id", "unknown")
        assay_config = get_formatted_assay_config(
            sample,
            assay_panel_repository=self.assay_panel_repository,
            assay_configuration_repository=self.assay_configuration_repository,
        )
        if not assay_config:
            raise setup_error(
                f"ASPC not registered for assay '{sample_assay}'",
                (
                    f"Sample '{sample.get('name', sample.get('_id'))}' requires coverage context for "
                    f"assay '{sample_assay}', but no active configuration can be resolved."
                ),
                hint="Create and activate the matching ASPC or its base configuration before opening coverage pages.",
            )

        assay_group = assay_config.get("asp_group", "unknown")
        assay_panel_doc = self.assay_panel_repository.get_asp(asp_name=sample_assay)
        if not assay_panel_doc:
            raise setup_error(
                f"ASP not registered for assay '{sample_assay}'",
                f"No active ASP exists for sample '{sample.get('name', sample.get('_id'))}'.",
                hint="Create and activate the matching ASP before opening coverage pages.",
            )
        gene_scope = list(assay_panel_doc.get("covered_genes") or [])

        cov_dict = self.coverage_repository.get_sample_coverage(str(sample["_id"])) or {}
        cov_dict = deepcopy(cov_dict)
        cov_dict.pop("_id", None)
        sample_payload = deepcopy(sample)
        sample_payload.pop("_id", None)

        filtered_dict = CoverageProcessingService.filter_genes_from_form(
            cov_dict,
            gene_scope,
            assay_group,
            grouped_coverage_repository=self.grouped_coverage_repository,
        )
        filtered_dict = CoverageProcessingService.find_low_covered_genes(
            filtered_dict,
            cov_cutoff,
            assay_group,
            grouped_coverage_repository=self.grouped_coverage_repository,
        )
        cov_table = CoverageProcessingService.coverage_table(filtered_dict, cov_cutoff)
        filtered_dict = CoverageProcessingService.organize_data_for_d3(filtered_dict)

        return {
            "coverage": filtered_dict,
            "cov_cutoff": cov_cutoff,
            "sample": sample_payload,
            "gene_scope": gene_scope,
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
        if not user.is_superuser and group not in set(user.asp_groups or []):
            raise forbidden_error(
                f"Assay group '{group}' is outside your scope",
                f"User '{user.username}' is not assigned to assay group '{group}'.",
                hint="Ask an administrator to assign the assay group, or use a superuser account.",
            )

        grouped_by_gene = defaultdict(dict)
        blacklisted = list(self.grouped_coverage_repository.get_regions_per_group(group) or [])
        for entry in blacklisted:
            if entry["region"] == "gene":
                grouped_by_gene[entry["gene"]]["gene"] = entry["_id"]
            elif entry["region"] == "CDS":
                grouped_by_gene[entry["gene"]]["CDS"] = entry
            elif entry["region"] == "probe":
                grouped_by_gene[entry["gene"]]["probe"] = entry

        return {"blacklisted": grouped_by_gene, "group": group}
