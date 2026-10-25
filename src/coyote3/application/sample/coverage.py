"""Coverage workflow service."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from coyote3.application.common.access import enforce_assay_group
from coyote3.application.common.assay_config import get_formatted_assay_config
from coyote3.application.common.release_resources import assay_resource, gene_list_resources
from coyote3.application.coverage.processing import CoverageProcessingService
from coyote3.domain.common.assay_filters import (
    get_sample_effective_genes,
    merge_sample_settings_with_assay_config,
)
from coyote3.domain.common.errors import setup_error
from coyote3.domain.common.sample_filters import normalize_sample_filters


class CoverageService:
    """Own coverage read and blacklist-view workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "CoverageService":
        """Build the service from the runtime store."""
        return cls(
            assay_configuration_repository=store.assay_configuration_repository,
            assay_panel_repository=store.assay_panel_repository,
            d4_coverage_repository=store.d4_coverage_repository,
            d4_coverage_blacklist_repository=store.d4_coverage_blacklist_repository,
        )

    def __init__(
        self,
        *,
        assay_configuration_repository: Any,
        assay_panel_repository: Any,
        d4_coverage_repository: Any,
        d4_coverage_blacklist_repository: Any,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.assay_configuration_repository = assay_configuration_repository
        self.assay_panel_repository = assay_panel_repository
        self.d4_coverage_repository = d4_coverage_repository
        self.d4_coverage_blacklist_repository = d4_coverage_blacklist_repository

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
        assay_panel_doc = assay_resource(assay_config)
        scoped_sample = merge_sample_settings_with_assay_config(sample, assay_config)
        filters = normalize_sample_filters(scoped_sample.get("filters"), asp_category="dna")
        selected = (filters.get("snv") or {}).get("snvlists") or []
        lists = gene_list_resources(assay_config, selected) if selected else {}
        _, gene_scope = get_sample_effective_genes(
            scoped_sample, assay_panel_doc, lists, target="snv"
        )

        cov_dict = self.d4_coverage_repository.get_sample_coverage(str(sample["_id"])) or {}
        cov_dict = deepcopy(cov_dict)
        cov_dict.pop("_id", None)
        sample_payload = deepcopy(sample)
        sample_payload.pop("_id", None)

        filtered_dict = CoverageProcessingService.filter_genes_from_form(
            cov_dict,
            gene_scope,
            assay_group,
            d4_coverage_blacklist_repository=self.d4_coverage_blacklist_repository,
        )
        filtered_dict = CoverageProcessingService.find_low_covered_genes(
            filtered_dict,
            cov_cutoff,
            assay_group,
            d4_coverage_blacklist_repository=self.d4_coverage_blacklist_repository,
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
        enforce_assay_group(user, group)

        grouped_by_gene = defaultdict(dict)
        blacklisted = list(self.d4_coverage_blacklist_repository.get_regions_per_group(group) or [])
        for entry in blacklisted:
            if entry["region"] == "gene":
                grouped_by_gene[entry["gene"]]["gene"] = entry["_id"]
            elif entry["region"] == "CDS":
                grouped_by_gene[entry["gene"]]["CDS"] = entry
            elif entry["region"] == "probe":
                grouped_by_gene[entry["gene"]]["probe"] = entry

        return {"blacklisted": grouped_by_gene, "group": group}
