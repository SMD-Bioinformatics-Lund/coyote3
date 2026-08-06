"""Sample catalog and sample workflow service."""

from __future__ import annotations

import os
from types import SimpleNamespace
from typing import Any

from api.application.common.assay_config import get_formatted_assay_config
from api.application.sample.catalog_filters import SampleCatalogFiltersMixin
from api.application.sample.catalog_mutations import SampleCatalogMutationsMixin
from api.config.constants import DEFAULT_ENVIRONMENT, primary_analysis_file_key
from api.infra.observability.operations import measured_operation

runtime_app = SimpleNamespace(config={})

FILE_DISPLAY_METADATA: dict[str, dict[str, str]] = {
    primary_analysis_file_key("dna", "SNV"): {
        "label": "VCF",
        "icon": "document-text",
        "missing_msg": "No VCF file available",
    },
    primary_analysis_file_key("dna", "CNV"): {
        "label": "CNV JSON",
        "icon": "clipboard-document-list",
        "missing_msg": "No CNV JSON available",
    },
    primary_analysis_file_key("dna", "TRANSLOCATION"): {
        "label": "Transloc VCF",
        "icon": "link",
        "missing_msg": "No Transloc VCF available",
    },
    primary_analysis_file_key("dna", "COVERAGE"): {
        "label": "Coverage JSON",
        "icon": "chart-bar",
        "missing_msg": "No coverage file available",
    },
    primary_analysis_file_key("dna", "BIOMARKER"): {
        "label": "Biomarkers JSON",
        "icon": "finger-print",
        "missing_msg": "No biomarkers file available",
    },
    primary_analysis_file_key("dna", "CNV_PROFILE"): {
        "label": "CNV Profile (image)",
        "icon": "photo",
        "missing_msg": "No CNV profile available",
    },
    primary_analysis_file_key("rna", "FUSION"): {
        "label": "Fusion Calls",
        "icon": "link",
        "missing_msg": "No fusion file available",
    },
    primary_analysis_file_key("rna", "EXPRESSION"): {
        "label": "Expression",
        "icon": "clipboard-document-list",
        "missing_msg": "No Expression file available",
    },
    primary_analysis_file_key("rna", "CLASSIFICATION"): {
        "label": "Classification",
        "icon": "document-text",
        "missing_msg": "No Classification file available",
    },
    primary_analysis_file_key("rna", "QC"): {
        "label": "QC",
        "icon": "chart-bar",
        "missing_msg": "No QC file available",
    },
}

FILE_COUNT_BADGE_METADATA: dict[str, tuple[str, str]] = {
    primary_analysis_file_key("dna", "SNV"): ("snvs", "SNVs"),
    primary_analysis_file_key("dna", "CNV"): ("cnvs", "CNVs"),
    primary_analysis_file_key("dna", "TRANSLOCATION"): ("transloc", "Translocs"),
    primary_analysis_file_key("rna", "FUSION"): ("fusions", "Fusions"),
    primary_analysis_file_key("rna", "EXPRESSION"): ("rna_expr", "Expr"),
    primary_analysis_file_key("rna", "CLASSIFICATION"): ("rna_class", "classes"),
    primary_analysis_file_key("rna", "QC"): ("rna_qc", "data"),
}


class SampleCatalogService(SampleCatalogMutationsMixin, SampleCatalogFiltersMixin):
    """Own sample-list and sample-context workflows for the API."""

    @classmethod
    def from_store(
        cls,
        store: Any,
        *,
        reported_samples_search_limit: int = 50,
        reports_base_path: str = "",
    ) -> "SampleCatalogService":
        """Build the service from the runtime store."""
        return cls(
            sample_repository=store.sample_repository,
            gene_list_repository=store.gene_list_repository,
            assay_panel_repository=store.assay_panel_repository,
            assay_configuration_repository=store.assay_configuration_repository,
            variant_repository=store.variant_repository,
            copy_number_variant_repository=store.copy_number_variant_repository,
            fusion_repository=store.fusion_repository,
            translocation_repository=store.translocation_repository,
            biomarker_repository=store.biomarker_repository,
            grouped_coverage_repository=store.grouped_coverage_repository,
            sample_comment_repository=store.sample_comment_repository,
            reported_samples_search_limit=reported_samples_search_limit,
            reports_base_path=reports_base_path,
        )

    def __init__(
        self,
        *,
        sample_repository: Any,
        gene_list_repository: Any,
        assay_panel_repository: Any,
        assay_configuration_repository: Any | None = None,
        variant_repository: Any,
        copy_number_variant_repository: Any,
        fusion_repository: Any,
        translocation_repository: Any,
        biomarker_repository: Any,
        grouped_coverage_repository: Any,
        sample_comment_repository: Any | None = None,
        reported_samples_search_limit: int = 50,
        reports_base_path: str = "",
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.sample_repository = sample_repository
        self.gene_list_repository = gene_list_repository
        self.assay_panel_repository = assay_panel_repository
        self.assay_configuration_repository = assay_configuration_repository
        self.variant_repository = variant_repository
        self.copy_number_variant_repository = copy_number_variant_repository
        self.fusion_repository = fusion_repository
        self.translocation_repository = translocation_repository
        self.biomarker_repository = biomarker_repository
        self.grouped_coverage_repository = grouped_coverage_repository
        self.sample_comment_repository = sample_comment_repository
        self.reported_samples_search_limit = int(reported_samples_search_limit or 50)
        self.reports_base_path = str(reports_base_path or "")

    def _get_formatted_assay_config(self, sample: dict) -> dict:
        """Resolve formatted assay config using injected repositories when available."""
        if self.assay_configuration_repository is None:
            return get_formatted_assay_config(sample)
        return get_formatted_assay_config(
            sample,
            assay_panel_repository=self.assay_panel_repository,
            assay_configuration_repository=self.assay_configuration_repository,
        )

    @staticmethod
    def _expected_file_keys_for_sample(sample: dict[str, Any], asp: dict[str, Any]) -> list[str]:
        """Return assay-configured file keys, defaulting to category-appropriate sample keys."""
        from api.contracts.schemas.assay import DNA_EXPECTED_FILE_OPTIONS, RNA_EXPECTED_FILE_OPTIONS

        raw = asp.get("expected_files")
        if isinstance(raw, list):
            keys = [str(item or "").strip() for item in raw if str(item or "").strip()]
            if keys:
                return keys
        omics = str(sample.get("omics_layer", "")).strip().lower()
        if omics == "rna":
            return list(RNA_EXPECTED_FILE_OPTIONS)
        return list(DNA_EXPECTED_FILE_OPTIONS)

    @staticmethod
    def _required_file_keys_for_sample(asp: dict[str, Any]) -> set[str]:
        """Return the assay-configured required file keys for a sample."""
        raw = asp.get("required_files")
        if not isinstance(raw, list):
            return set()
        return {str(item or "").strip() for item in raw if str(item or "").strip()}

    @classmethod
    def _file_rows_for_sample(
        cls, sample: dict[str, Any], asp: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Build Files & QC rows from assay-configured expected file keys."""
        data_counts = dict(sample.get("data_counts") or {})
        sample_files = sample.get("files") if isinstance(sample.get("files"), dict) else {}
        required_keys = cls._required_file_keys_for_sample(asp)
        rows: list[dict[str, Any]] = []
        for key in cls._expected_file_keys_for_sample(sample, asp):
            meta = FILE_DISPLAY_METADATA.get(key)
            if not meta:
                continue
            file_doc = sample_files.get(key)
            file_meta = file_doc if isinstance(file_doc, dict) else {}
            path = (
                file_meta.get("path")
                if isinstance(file_meta, dict)
                else file_doc
                if isinstance(file_doc, str)
                else None
            )
            if not path:
                path = sample.get(key)
            required = key in required_keys
            path_exists = bool(path) and os.path.exists(str(path))
            size_bytes = file_meta.get("size_bytes") if isinstance(file_meta, dict) else None
            if size_bytes is None and path_exists:
                try:
                    size_bytes = os.path.getsize(str(path))
                except OSError:
                    size_bytes = None
            count_key, count_suffix = FILE_COUNT_BADGE_METADATA.get(key, ("", ""))
            count_badge = None
            if count_key and data_counts.get(count_key):
                count_badge = f"{data_counts[count_key]} {count_suffix}"
            elif key == primary_analysis_file_key("dna", "COVERAGE") and data_counts.get("cov"):
                count_badge = "Loaded"
            elif key == primary_analysis_file_key("dna", "BIOMARKER") and data_counts.get(
                "biomarkers"
            ):
                count_badge = "Loaded"
            if path and path_exists:
                status_label = "Uploaded"
                status_tone = "ok"
                warning_message = None
            elif path and not path_exists:
                status_label = "Broken Path"
                status_tone = "error"
                warning_message = "Sample references a file path that is not currently readable."
            elif required:
                status_label = "Required Missing"
                status_tone = "error"
                warning_message = "Required file not uploaded for this sample."
            else:
                status_label = "Optional Missing"
                status_tone = "warning"
                warning_message = "Optional file not uploaded for this sample."
            rows.append(
                {
                    "key": key,
                    "label": meta["label"],
                    "path": path,
                    "present": bool(path),
                    "exists": path_exists,
                    "size_bytes": size_bytes,
                    "checksum": file_meta.get("checksum") if isinstance(file_meta, dict) else None,
                    "registered_on": file_meta.get("registered_on")
                    if isinstance(file_meta, dict)
                    else None,
                    "required": required,
                    "icon": meta["icon"],
                    "missing_msg": meta["missing_msg"],
                    "count_badge": count_badge,
                    "status_label": status_label,
                    "status_tone": status_tone,
                    "warning_message": warning_message,
                }
            )
        return rows

    @measured_operation("query.samples")
    def samples_payload(
        self,
        *,
        user,
        status: str,
        search_str: str,
        search_mode: str,
        page: int,
        per_page: int,
        live_page: int,
        per_live_page: int,
        done_page: int,
        per_done_page: int,
        profile_scope: str,
        panel_type: str | None,
        panel_tech: str | None,
        assay_group: str | None,
        limit_done_samples: int | None,
    ) -> dict[str, Any]:
        """Return the sample list payload for the catalog view.

        Args:
            user: Authenticated user requesting the catalog.
            status: Requested sample status filter.
            search_str: Free-text search string.
            search_mode: Search mode selected by the client.
            page: Current combined page number.
            per_page: Combined page size.
            live_page: Current page for live samples.
            per_live_page: Page size for live samples.
            done_page: Current page for completed samples.
            per_done_page: Page size for completed samples.
            profile_scope: Environment/profile scope to apply.
            panel_type: Optional panel-type filter.
            panel_tech: Optional panel-technology filter.
            assay_group: Optional assay-group filter.
            limit_done_samples: Optional cap for completed samples.

        Returns:
            dict[str, Any]: Normalized sample catalog payload.
        """
        if limit_done_samples is None:
            limit_done_samples = self.reported_samples_search_limit

        if panel_type and panel_tech and assay_group:
            assay_list = user.asp_map.get(panel_type, {}).get(panel_tech, {}).get(assay_group, [])
            accessible_assays = (
                assay_list if user.is_superuser else [a for a in assay_list if a in user.asp_ids]
            )
        elif user.is_superuser:
            accessible_assays = None
        else:
            accessible_assays = user.asp_ids

        normalized_scope = (profile_scope or "").strip().lower()
        use_all_profiles = normalized_scope == "all"
        query_envs = None if user.is_superuser and use_all_profiles else list(user.envs)
        if not user.is_superuser and not use_all_profiles:
            query_envs = (
                [DEFAULT_ENVIRONMENT] if DEFAULT_ENVIRONMENT in user.envs else list(user.envs)
            )
        elif user.is_superuser and not use_all_profiles:
            query_envs = [DEFAULT_ENVIRONMENT]

        live_offset = max(0, (live_page - 1) * per_live_page)
        done_offset = max(0, (done_page - 1) * per_done_page)
        live_fetch_limit = per_live_page + 1
        done_fetch_limit = per_done_page + 1
        search_applied = bool((search_str or "").strip())

        has_next_live = False
        has_next_done = False

        done_limit = None if search_applied else done_fetch_limit
        if not search_applied and limit_done_samples:
            done_limit = min(done_fetch_limit, limit_done_samples + 1)

        done_samples = list(
            self.sample_repository.get_samples(
                user_assays=accessible_assays,
                user_envs=query_envs,
                status="done",
                search_str=search_str,
                report=True,
                limit=done_limit,
                offset=0 if search_applied else done_offset,
                use_cache=True,
                reload=False,
            )
            or []
        )
        if not search_applied and len(done_samples) > per_done_page:
            has_next_done = True
            done_samples = done_samples[:per_done_page]

        live_samples = list(
            self.sample_repository.get_samples(
                user_assays=accessible_assays,
                user_envs=query_envs,
                status="live",
                search_str=search_str,
                report=False,
                limit=None if search_applied else live_fetch_limit,
                offset=0 if search_applied else live_offset,
                use_cache=True,
                reload=False,
            )
            or []
        )
        if not search_applied and len(live_samples) > per_live_page:
            has_next_live = True
            live_samples = live_samples[:per_live_page]

        for sample in done_samples:
            sample["last_report_time_created"] = sample.get("latest_report_on") or 0

        return {
            "live_samples": live_samples,
            "done_samples": done_samples,
            "status": status,
            "search_mode": search_mode,
            "sample_view": "all",
            "profile_scope": "all" if use_all_profiles else DEFAULT_ENVIRONMENT,
            "page": page,
            "per_page": per_page,
            "live_page": live_page,
            "live_per_page": per_live_page,
            "done_page": done_page,
            "done_per_page": per_done_page,
            "has_next_live": has_next_live,
            "has_next_done": has_next_done,
            "panel_type": panel_type,
            "panel_tech": panel_tech,
            "assay_group": assay_group,
        }

    def navigation_counts_payload(self, *, user, profile_scope: str) -> dict[str, Any]:
        """Return current-user live sample counts for the assay navigation tree."""
        normalized_scope = (profile_scope or "").strip().lower()
        use_all_profiles = normalized_scope == "all"
        if user.is_superuser:
            accessible_assays = None
        else:
            accessible_assays = list(user.asp_ids)

        if user.is_superuser and use_all_profiles:
            query_envs = None
        elif not user.is_superuser and not use_all_profiles:
            query_envs = (
                [DEFAULT_ENVIRONMENT] if DEFAULT_ENVIRONMENT in user.envs else list(user.envs)
            )
        elif user.is_superuser:
            query_envs = [DEFAULT_ENVIRONMENT]
        else:
            query_envs = list(user.envs)

        by_asp = self.sample_repository.count_live_samples_by_asp(
            user_assays=accessible_assays,
            user_envs=query_envs,
        )
        counts: dict[str, int] = {}
        for asp in self.assay_panel_repository.get_all_asps() or []:
            asp_id = str(asp.get("asp_id") or "").strip()
            if not asp_id:
                continue
            category = str(asp.get("asp_category") or "assay").strip().lower()
            raw_family = str(asp.get("asp_family") or "").strip().lower()
            family = "panel" if raw_family.startswith("panel") else (raw_family or "assay")
            group = str(asp.get("asp_group") or "unassigned").strip().lower()
            key = f"{category}:{family}:{group}"
            counts[key] = counts.get(key, 0) + by_asp.get(asp_id, 0)

        return {
            "counts": counts,
            "profile_scope": "all" if use_all_profiles else DEFAULT_ENVIRONMENT,
        }
