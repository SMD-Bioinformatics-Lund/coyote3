"""Sample catalog and sample workflow service."""

from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace
from typing import Any

from api.application.common.assay_config import get_formatted_assay_config
from api.application.sample.catalog_filters import SampleCatalogFiltersMixin
from api.application.sample.catalog_mutations import SampleCatalogMutationsMixin
from api.config.constants import (
    DEFAULT_ENVIRONMENT,
    analysis_type_for_file_key,
    manifest_file_preload_keys,
)
from api.infra.observability.operations import measured_operation

runtime_app = SimpleNamespace(config={})


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

    def _get_formatted_assay_config(
        self, sample: dict, *, use_sample_revision: bool = True
    ) -> dict:
        """Resolve formatted assay config using injected repositories when available."""
        if self.assay_configuration_repository is None:
            return get_formatted_assay_config(sample, use_sample_revision=use_sample_revision)
        return get_formatted_assay_config(
            sample,
            assay_panel_repository=self.assay_panel_repository,
            assay_configuration_repository=self.assay_configuration_repository,
            use_sample_revision=use_sample_revision,
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
        omics_layer = str(sample.get("omics_layer") or "dna").strip().lower()
        preload_keys = manifest_file_preload_keys(omics_layer)
        required_keys = cls._required_file_keys_for_sample(asp)
        rows: list[dict[str, Any]] = []
        for key in cls._expected_file_keys_for_sample(sample, asp):
            analysis_type = analysis_type_for_file_key(omics_layer, key)
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
            data_count = data_counts.get(preload_keys.get(key, ""))
            if path and path_exists:
                availability = "available"
            elif path and not path_exists:
                availability = "unreadable"
            elif required:
                availability = "required_missing"
            else:
                availability = "optional_missing"
            rows.append(
                {
                    "key": key,
                    "analysis_type": analysis_type,
                    "path": path,
                    "present": bool(path),
                    "exists": path_exists,
                    "size_bytes": size_bytes,
                    "checksum": file_meta.get("checksum") if isinstance(file_meta, dict) else None,
                    "registered_on": file_meta.get("registered_on")
                    if isinstance(file_meta, dict)
                    else None,
                    "required": required,
                    "data_count": data_count if isinstance(data_count, int | float) else None,
                    "availability": availability,
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
        added_from: datetime | None = None,
        added_until: datetime | None = None,
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
                added_from=added_from,
                added_until=added_until,
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
                added_from=added_from,
                added_until=added_until,
            )
            or []
        )
        if not search_applied and len(live_samples) > per_live_page:
            has_next_live = True
            live_samples = live_samples[:per_live_page]

        self._attach_biomarker_values([*live_samples, *done_samples])

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
            "added_from": added_from,
            "added_until": added_until,
        }

    @staticmethod
    def _flatten_biomarker_values(value: Any, *, prefix: str = "") -> dict[str, Any]:
        """Flatten nested biomarker values into deterministic export columns."""
        if not isinstance(value, dict):
            return {prefix: value} if prefix else {}
        flattened: dict[str, Any] = {}
        for key in sorted(value):
            if key in {"_id", "SAMPLE_ID", "biomarker_id", "name"}:
                continue
            child_prefix = f"{prefix}.{key}" if prefix else str(key)
            child = value[key]
            if isinstance(child, dict):
                flattened.update(
                    SampleCatalogService._flatten_biomarker_values(child, prefix=child_prefix)
                )
            else:
                flattened[child_prefix] = child
        return flattened

    def _attach_biomarker_values(self, samples: list[dict[str, Any]]) -> None:
        """Attach flat biomarker values to sample rows through one bulk repository call."""
        bulk_getter = getattr(self.biomarker_repository, "get_samples_biomarkers", None)
        if not callable(bulk_getter):
            return
        sample_ids = [str(sample.get("_id")) for sample in samples if sample.get("_id") is not None]
        grouped = bulk_getter(sample_ids)
        for sample in samples:
            sample_id = str(sample.get("_id") or "")
            merged: dict[str, Any] = {}
            for document in grouped.get(sample_id, []):
                values = self._flatten_biomarker_values(document)
                for key, value in values.items():
                    if key not in merged:
                        merged[key] = value
                        continue
                    document_name = str(document.get("name") or "biomarker").strip()
                    merged[f"{document_name}.{key}"] = value
            sample["biomarker_values"] = merged

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
