"""Mutable sample catalog workflows and report-context composition."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from api.config.clinical_vocabulary import CLINICAL_VOCABULARY
from api.domain.common.errors import api_error
from api.domain.common.sample_filters import (
    merge_filter_defaults,
    normalize_sample_filters,
    sample_filters_from_aspc_filters,
)


class SampleCatalogMutationsMixin:
    """Provide sample filter mutations, comments, and report context."""

    def genelist_items_payload(self, *, sample: dict, target: str | None = None) -> dict[str, Any]:
        """Return selectable genelist items for a sample.

        Args:
            sample: Sample payload used to resolve active genelists.

        Returns:
            dict[str, Any]: Genelist item payload for the UI.
        """
        target = self._normalize_list_target(sample, target)
        asp = self.assay_panel_repository.get_asp(sample.get("asp_id"))
        if target == "all":
            items = []
            for scoped_target in ("snv", "cnv", "translocation", "fusion"):
                items.extend(
                    self._genelist_options_for_target(sample=sample, asp=asp, target=scoped_target)
                )
            items = list({item["id"]: item for item in items}.values())
        else:
            items = self._genelist_options_for_target(sample=sample, asp=asp, target=target)
        return {"items": items}

    def effective_genes_payload(self, *, sample: dict, target: str | None = None) -> dict[str, Any]:
        """Return the effective gene set for a sample.

        Args:
            sample: Sample payload used to resolve active filters.

        Returns:
            dict[str, Any]: Effective genes and panel coverage counts.
        """
        target = self._normalize_list_target(sample, target)
        assay = sample.get("asp_id")
        if not assay:
            raise api_error(400, "Sample is missing the 'asp_id' field")
        asp = self.assay_panel_repository.get_asp(assay)
        items, asp_covered_genes, _asp_group = self._effective_genes_for_target(
            sample=sample, asp=asp, target=target
        )
        return {
            "items": items,
            "asp_covered_genes_count": len(asp_covered_genes),
            "target": target,
        }

    def edit_context_payload(self, *, sample: dict) -> dict[str, Any]:
        """Return edit-context data for a sample.

        Args:
            sample: Sample payload being edited.

        Returns:
            dict[str, Any]: Sample, panel, and variant-stat context.
        """
        assay = sample.get("asp_id")
        if not assay:
            raise api_error(400, "Sample is missing the 'asp_id' field")
        asp = self.assay_panel_repository.get_asp(assay)

        if sample.get("filters") is None:
            assay_config = self._get_formatted_assay_config(sample)
            analysis_intents = list(assay_config.get("analysis_intents") or ["somatic"])
            default_filters = sample_filters_from_aspc_filters(
                assay_config.get("filters"),
                str(sample.get("omics_layer") or "dna"),
                analysis_intents=analysis_intents,
            )
            self.sample_repository.reset_sample_settings(
                sample.get("_id"),
                default_filters,
                aspc={
                    "_id": assay_config.get("_id"),
                    "aspc_id": assay_config.get("aspc_id"),
                    "version": assay_config.get("version"),
                },
                analysis_intents=analysis_intents,
                aspc_resolution=assay_config.get("aspc_resolution"),
            )
            sample = self.sample_repository.get_sample(sample["_id"])

        filters = self._sample_filters(sample)
        adhoc_scopes = self._normalized_adhoc_genes(filters) or {}

        sample = deepcopy(sample)
        sample_filters = self._sample_filters(sample)
        assay_config = self._get_formatted_assay_config(sample)
        sample_filters = merge_filter_defaults(
            sample_filters,
            assay_config.get("filters"),
            omics_layer=str(sample.get("omics_layer") or "dna"),
        )
        for scope, entry in adhoc_scopes.items():
            if scope in {"snv", "cnv", "fusion", "translocation"}:
                sample_filters.setdefault(scope, {})["adhoc_genes"] = entry
        sample["filters"] = sample_filters

        variant_stats_raw = self.variant_repository.get_variant_stats(str(sample.get("_id")))
        analysis_counts_raw, analysis_counts_filtered, variant_stats_filtered = (
            self._analysis_counts(
                sample=sample,
                asp=asp,
                variant_stats_raw=variant_stats_raw,
            )
        )
        analysis_sections = list(assay_config.get("analysis_types") or [])
        biomarker_rows = list(
            self.biomarker_repository.get_sample_biomarkers(str(sample.get("_id"))) or []
        )
        sample_comments = []
        if self.sample_comment_repository is not None:
            sample_comments = list(
                self.sample_comment_repository.list_sample_comments(str(sample.get("_id"))) or []
            )

        response_sample = deepcopy(sample)
        response_sample["filters"] = self._sample_filters(sample)
        latest_assay_config = self._get_formatted_assay_config(sample, use_sample_revision=False)
        current_revision = str(sample.get("current_aspc_id") or "")
        latest_revision = str(latest_assay_config.get("_id") or "")
        return {
            "sample": response_sample,
            "comments": sample_comments,
            "asp": asp,
            "sample_expected_files": self._file_rows_for_sample(sample, asp),
            "snv_genelist_options": self._genelist_options_for_target(
                sample=sample, asp=asp, target="snv"
            ),
            "cnvlist_options": self._genelist_options_for_target(
                sample=sample, asp=asp, target="cnv"
            ),
            "fusionlist_options": self._genelist_options_for_target(
                sample=sample, asp=asp, target="fusion"
            ),
            "fusion_caller_options": list(CLINICAL_VOCABULARY.fusion_callers),
            "fusion_annotation_metadata": CLINICAL_VOCABULARY.fusion_annotation_metadata(),
            "selected_gene_panels": self._selected_gene_panel_summary(sample=sample, asp=asp),
            "analysis_sections": analysis_sections,
            "analysis_counts_raw": analysis_counts_raw,
            "analysis_counts_filtered": analysis_counts_filtered,
            "variant_stats_raw": variant_stats_raw,
            "variant_stats_filtered": variant_stats_filtered,
            "biomarkers": biomarker_rows,
            "aspc_update": {
                "available": bool(latest_revision and latest_revision != current_revision),
                "current_aspc_id": sample.get("current_aspc_key"),
                "current_version": sample.get("current_aspc_version"),
                "latest_aspc_id": latest_assay_config.get("aspc_id"),
                "latest_version": latest_assay_config.get("version"),
            },
        }

    def apply_genelists(
        self, *, sample: dict, payload: dict[str, Any], sample_id: str, target: str | None = None
    ) -> dict[str, Any]:
        """Persist selected genelists for a sample.

        Args:
            sample: Sample payload being updated.
            payload: Request payload containing selected genelist IDs.
            sample_id: Sample identifier reported in the response.

        Returns:
            dict[str, Any]: Mutation response payload.
        """
        requested_target = (
            target if isinstance(target, str) and target.strip() else payload.get("list_type")
        )
        target = self._normalize_list_target(sample, requested_target)
        target_filters = self._target_filters(sample, target)
        genelist_ids = payload.get("isgl_ids", [])
        if not isinstance(genelist_ids, list):
            raise api_error(400, "Invalid isgl_ids payload")
        if target == "all":
            raise api_error(400, "Gene lists must be applied to one analysis type")
        normalized_ids = self._validated_genelist_ids(genelist_ids, target=target)
        target_filters[self._filter_key_for_target(target)] = normalized_ids
        filters = self._replace_target_filters(sample, target, target_filters)
        self.sample_repository.update_sample_filters(sample.get("_id"), filters)
        return {
            "status": "ok",
            "sample_id": sample_id,
            "action": "apply_genelists",
            "genelist_ids": normalized_ids,
            "list_type": target,
        }

    def save_adhoc_genes(
        self, *, sample: dict, payload: dict[str, Any], sample_id: str, target: str | None = None
    ) -> dict[str, Any]:
        """Persist ad hoc genes for a sample.

        Args:
            sample: Sample payload being updated.
            payload: Request payload containing genes and label.
            sample_id: Sample identifier reported in the response.

        Returns:
            dict[str, Any]: Mutation response payload.
        """
        genes_raw = payload.get("genes", "")
        genes = [g.strip() for g in re.split(r"[ ,\n]+", genes_raw) if g.strip()]
        genes.sort()
        label = payload.get("label") or "adhoc"
        requested_target = (
            target if isinstance(target, str) and target.strip() else payload.get("list_type")
        )
        target = self._normalize_list_target(sample, requested_target)
        target_filters = self._target_filters(sample, target)
        target_filters["adhoc_genes"] = {
            "label": label,
            "genes": genes,
        }
        filters = self._replace_target_filters(sample, target, target_filters)
        self.sample_repository.update_sample_filters(sample.get("_id"), filters)
        return {
            "status": "ok",
            "sample_id": sample_id,
            "action": "save_adhoc_genes",
            "label": label,
            "gene_count": len(genes),
            "list_type": target,
        }

    def clear_adhoc_genes(
        self, *, sample: dict, sample_id: str, target: str | None = None
    ) -> dict[str, Any]:
        """Remove ad hoc genes from a sample filter set.

        Args:
            sample: Sample payload being updated.
            sample_id: Sample identifier reported in the response.

        Returns:
            dict[str, Any]: Mutation response payload.
        """
        requested_target = target if isinstance(target, str) and target.strip() else None
        target = self._normalize_list_target(sample, requested_target)
        target_filters = self._target_filters(sample, target)
        if not target_filters.get("adhoc_genes"):
            return {"status": "ok", "sample_id": sample_id, "action": "clear_adhoc_genes"}
        target_filters.pop("adhoc_genes", None)
        filters = self._replace_target_filters(sample, target, target_filters)
        self.sample_repository.update_sample_filters(sample.get("_id"), filters)
        return {
            "status": "ok",
            "sample_id": sample_id,
            "action": "clear_adhoc_genes",
            "list_type": target,
        }

    def report_context_payload(
        self, *, sample: dict, report_id: str, sample_id: str
    ) -> dict[str, Any]:
        """Return report-download context for a sample report.

        Args:
            sample: Sample payload linked to the report.
            report_id: Report identifier to load.
            sample_id: Sample identifier used for lookup.

        Returns:
            dict[str, Any]: Report metadata and resolved file path.
        """
        report = self.sample_repository.get_report(sample_id, report_id)
        if not report:
            raise api_error(404, "Report not found")
        report_name = report.get("report_name")
        filepath = report.get("filepath")
        pdf_report_name = report.get("pdf_report_name")
        pdf_filepath = report.get("pdf_filepath")

        if not filepath and report_name:
            assay_config = self._get_formatted_assay_config(sample)
            report_sub_dir = assay_config.get("reporting", {}).get("report_path", "")
            filepath = f"{self.reports_base_path}/{report_sub_dir}/{report_name}"

        findings: list[dict[str, Any]] = []
        if self.reported_variant_repository is not None:
            findings = self.reported_variant_repository.list_reported_variants(
                {
                    "sample_oid": sample.get("_id"),
                    "report_oid": report.get("_id"),
                }
            )
        analysis_counts: dict[str, int] = {}
        for finding in findings:
            analysis_type = str(finding.get("analysis_type") or "OTHER").upper()
            analysis_counts[analysis_type] = analysis_counts.get(analysis_type, 0) + 1

        return {
            "sample_id": sample_id,
            "report_id": report_id,
            "report_name": report_name,
            "filepath": filepath,
            "pdf_report_name": pdf_report_name,
            "pdf_filepath": pdf_filepath,
            "asp_id": report.get("asp_id"),
            "subpanel_id": report.get("subpanel_id"),
            "environment": report.get("environment"),
            "author": report.get("author"),
            "time_created": report.get("time_created"),
            "finding_count": len(findings),
            "analysis_counts": analysis_counts,
            "findings": findings,
        }

    def add_sample_comment(self, *, sample_id: str, doc: dict[str, Any]) -> None:
        """Persist a sample comment."""
        self.sample_repository.add_sample_comment(sample_id, doc)

    def set_sample_comment_hidden(self, *, sample_id: str, comment_id: str, hidden: bool) -> None:
        """Hide or unhide a sample comment."""
        sample = self.sample_repository.get_sample(sample_id)
        sample_oid = str(sample.get("_id") or sample_id)
        if hidden:
            self.sample_repository.hide_sample_comment(sample_oid, comment_id)
            return
        self.sample_repository.unhide_sample_comment(sample_oid, comment_id)

    def replace_sample_filters(self, *, sample: dict, filters: dict[str, Any]) -> None:
        """Replace the stored filters for a sample."""
        normalized = normalize_sample_filters(
            filters,
            omics_layer=str(sample.get("omics_layer") or "dna"),
            analysis_intents=sample.get("analysis_intents"),
            canonical=True,
        )
        assay_config = self._get_formatted_assay_config(sample)
        normalized = merge_filter_defaults(
            normalized,
            assay_config.get("filters"),
            omics_layer=str(sample.get("omics_layer") or "dna"),
            analysis_intents=sample.get("analysis_intents"),
        )
        normalized = self._validate_filter_genelists(normalized)
        self.sample_repository.update_sample_filters(sample.get("_id"), normalized)

    def apply_latest_aspc(self, *, sample: dict) -> dict[str, Any]:
        """Apply the active ASPC revision to a sample by explicit user action."""
        assay_config = self._get_formatted_assay_config(sample, use_sample_revision=False)
        analysis_intents = list(assay_config.get("analysis_intents") or ["somatic"])
        filters = sample_filters_from_aspc_filters(
            assay_config.get("filters"),
            str(sample.get("omics_layer") or "dna"),
            analysis_intents=analysis_intents,
        )
        filters = self._validate_filter_genelists(filters)
        self.sample_repository.update_sample_filters(
            sample.get("_id"),
            filters,
            aspc={
                "_id": assay_config.get("_id"),
                "aspc_id": assay_config.get("aspc_id"),
                "version": assay_config.get("version"),
            },
            analysis_intents=analysis_intents,
            aspc_resolution=assay_config.get("aspc_resolution"),
        )
        return {
            "aspc_id": assay_config.get("aspc_id"),
            "version": assay_config.get("version"),
        }

    def reset_sample_filters(self, *, sample: dict, assay_config: dict) -> None:
        """Reset a sample's filters from assay defaults."""
        default_filters = sample_filters_from_aspc_filters(
            assay_config.get("filters"),
            str(sample.get("omics_layer") or "dna"),
            analysis_intents=sample.get("analysis_intents"),
        )
        default_filters = self._validate_filter_genelists(default_filters)
        self.sample_repository.reset_sample_settings(
            sample.get("_id"),
            default_filters,
            aspc={
                "_id": assay_config.get("_id"),
                "aspc_id": assay_config.get("aspc_id"),
                "version": assay_config.get("version"),
            },
            analysis_intents=list(assay_config.get("analysis_intents") or ["somatic"]),
            aspc_resolution=assay_config.get("aspc_resolution"),
        )

    def add_coverage_blacklist(
        self, *, gene: str, coord: str | None, region: str, smp_grp: str
    ) -> None:
        """Create a coverage blacklist entry."""
        if coord:
            sanitized_coord = str(coord).replace(":", "_").replace("-", "_")
            self.grouped_coverage_repository.blacklist_coord(gene, sanitized_coord, region, smp_grp)
            return
        self.grouped_coverage_repository.blacklist_gene(gene, smp_grp)

    def remove_coverage_blacklist(self, *, obj_id: str) -> None:
        """Delete a coverage blacklist entry."""
        self.grouped_coverage_repository.remove_blacklist(obj_id)

    def get_coverage_blacklist_entry(self, *, obj_id: str) -> dict | None:
        """Return a coverage blacklist entry."""
        return self.grouped_coverage_repository.get_blacklist_entry(obj_id)


__all__ = ["SampleCatalogMutationsMixin"]
