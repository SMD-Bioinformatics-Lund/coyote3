"""Coverage workflow service."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from coyote3.application.common.access import enforce_assay_group
from coyote3.application.common.assay_config import get_formatted_assay_config
from coyote3.application.common.release_resources import assay_resource, gene_list_resources
from coyote3.application.coverage.processing import CoverageProcessingService
from coyote3.domain.common.errors import setup_error, validation_error


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

    def sample_payload(
        self, *, sample: dict, cov_cutoff: int, gene_list_id: str | None = None
    ) -> dict[str, Any]:
        """Return low coverage within the sample's captured assay scope.

        Args:
            sample: Sample payload to inspect.
            cov_cutoff: Coverage threshold for low-coverage detection.
            gene_list_id: Optional captured gene list narrowing the assay scope.
                None uses the complete assay scope; a selected list containing
                no genes matches no measurements.

        Returns:
            Coverage charts, summary rows and gene scope. A nonempty assay
            covered_genes list defines scope; otherwise use ingested coverage genes.
            Finding filters do not affect coverage eligibility.

        Raises:
            AppError: The applied configuration or its captured assay is unavailable
                or fails integrity validation, or the selected list is unavailable.
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
        cov_dict = self.d4_coverage_repository.get_sample_coverage(str(sample["_id"])) or {}
        cov_dict = deepcopy(cov_dict)
        cov_dict.pop("_id", None)
        scope_genes = assay_panel_doc.get("covered_genes") or CoverageProcessingService._genes_map(
            cov_dict
        )
        gene_scope = sorted({str(gene).strip() for gene in scope_genes if str(gene).strip()})
        lists = gene_list_resources(assay_config)
        if gene_list_id is not None:
            if gene_list_id not in lists:
                raise validation_error("Choose a gene list from the sample's applied configuration")
            gene_scope = sorted(
                set(gene_scope).intersection(lists[gene_list_id].get("genes") or [])
            )
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
            "gene_list_id": gene_list_id,
            "gene_lists": [
                {"id": identity, "label": row.get("displayname") or identity}
                for identity, row in sorted(lists.items())
            ],
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
