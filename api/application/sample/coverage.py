"""Coverage workflow service."""

from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any

from api.application.coverage.processing import CoverageProcessingService
from api.config.constants import DEFAULT_ENVIRONMENT
from api.domain.common.errors import forbidden_error, setup_error
from api.domain.common.sample_filters import sample_filter_section


class CoverageService:
    """Own coverage read and blacklist-view workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "CoverageService":
        """Build the service from the runtime store."""
        return cls(
            assay_configuration_repository=store.assay_configuration_repository,
            assay_panel_repository=store.assay_panel_repository,
            gene_list_repository=store.gene_list_repository,
            coverage_repository=store.coverage_repository,
            grouped_coverage_repository=store.grouped_coverage_repository,
        )

    def __init__(
        self,
        *,
        assay_configuration_repository: Any,
        assay_panel_repository: Any,
        gene_list_repository: Any,
        coverage_repository: Any,
        grouped_coverage_repository: Any,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.assay_configuration_repository = assay_configuration_repository
        self.assay_panel_repository = assay_panel_repository
        self.gene_list_repository = gene_list_repository
        self.coverage_repository = coverage_repository
        self.grouped_coverage_repository = grouped_coverage_repository

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
        sample_profile = sample.get("profile", DEFAULT_ENVIRONMENT)
        assay_config = self.assay_configuration_repository.get_aspc_no_meta(
            sample_assay, sample_profile
        )
        if not assay_config:
            raise setup_error(
                f"ASPC not registered for assay '{sample_assay}' in environment '{sample_profile}'",
                (
                    f"Sample '{sample.get('name', sample.get('_id'))}' requires coverage context for "
                    f"assay '{sample_assay}' in environment '{sample_profile}', but no ASPC exists."
                ),
                hint="Create and activate the ASPC before opening coverage pages for this sample.",
            )

        assay_group = assay_config.get("assay_group", "unknown")
        assay_panel_doc = self.assay_panel_repository.get_asp(asp_name=sample_assay)
        sample_filters = sample_filter_section(
            sample.get("filters"),
            "snv",
            omics_layer=str(sample.get("omics_layer") or "dna"),
        )
        checked_snvlists = sample_filters.get("snvlists", [])

        if checked_snvlists:
            checked_snvlists_genes_dict = self.gene_list_repository.get_isgl_by_ids(
                checked_snvlists
            )
            _genes_covered_in_panel, filter_genes = effective_genes_resolver(
                sample,
                assay_panel_doc,
                checked_snvlists_genes_dict,
            )
        else:
            asp_id = assay_panel_doc.get("asp_id")
            if not asp_id:
                raise setup_error(
                    f"ASP for assay '{sample_assay}' is incomplete",
                    "The ASP exists but is missing the required 'asp_id' field used by coverage views.",
                    hint="Repair the ASP document and ensure asp_id is populated.",
                    status_code=500,
                )
            checked_snvlists = [asp_id]
            filter_genes = assay_panel_doc.get("covered_genes", [])

        cov_dict = self.coverage_repository.get_sample_coverage(str(sample["_id"])) or {}
        cov_dict = deepcopy(cov_dict)
        cov_dict.pop("_id", None)
        sample_payload = deepcopy(sample)
        sample_payload.pop("_id", None)

        filtered_dict = CoverageProcessingService.filter_genes_from_form(
            cov_dict,
            filter_genes,
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
            "snvlists": checked_snvlists,
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
        if not user.is_superuser and group not in set(user.assay_groups or []):
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
