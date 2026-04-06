"""Sample catalog and sample workflow service."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from api.http import api_error, get_formatted_assay_config
from api.runtime_state import app as runtime_app


class SampleCatalogService:
    """Own sample-list and sample-context workflows for the API."""

    @classmethod
    def from_store(cls, store: Any) -> "SampleCatalogService":
        """Build the service from the shared store."""
        return cls(
            sample_handler=store.sample_handler,
            gene_list_handler=store.gene_list_handler,
            assay_panel_handler=store.assay_panel_handler,
            variant_handler=store.variant_handler,
            grouped_coverage_handler=store.grouped_coverage_handler,
        )

    def __init__(
        self,
        *,
        sample_handler: Any,
        gene_list_handler: Any,
        assay_panel_handler: Any,
        variant_handler: Any,
        grouped_coverage_handler: Any,
    ) -> None:
        """Create the service with explicit injected handlers."""
        self.sample_handler = sample_handler
        self.gene_list_handler = gene_list_handler
        self.assay_panel_handler = assay_panel_handler
        self.variant_handler = variant_handler
        self.grouped_coverage_handler = grouped_coverage_handler

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
            limit_done_samples = runtime_app.config.get("REPORTED_SAMPLES_SEARCH_LIMIT", 50)

        if panel_type and panel_tech and assay_group:
            assay_list = user.asp_map.get(panel_type, {}).get(panel_tech, {}).get(assay_group, [])
            accessible_assays = [a for a in assay_list if a in user.assays]
        else:
            accessible_assays = user.assays

        normalized_scope = (profile_scope or "").strip().lower()
        use_all_profiles = normalized_scope == "all"
        query_envs = list(user.envs)
        if not use_all_profiles:
            query_envs = ["production"] if "production" in user.envs else list(user.envs)

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
            self.sample_handler.get_samples(
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
            self.sample_handler.get_samples(
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
            sample["last_report_time_created"] = (
                sample["reports"][-1]["time_created"]
                if sample.get("reports") and sample["reports"][-1].get("time_created")
                else 0
            )

        return {
            "live_samples": live_samples,
            "done_samples": done_samples,
            "status": status,
            "search_mode": search_mode,
            "sample_view": "all",
            "profile_scope": "all" if use_all_profiles else "production",
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

    def genelist_items_payload(self, *, sample: dict) -> dict[str, Any]:
        """Return selectable genelist items for a sample.

        Args:
            sample: Sample payload used to resolve active genelists.

        Returns:
            dict[str, Any]: Genelist item payload for the UI.
        """
        query = {"asp_name": sample.get("assay"), "is_active": True}
        isgls = list(self.gene_list_handler.get_isgl_by_asp(**query) or [])
        return {
            "items": [
                {
                    "isgl_id": str(gl["isgl_id"]),
                    "name": gl["displayname"],
                    "version": gl.get("version"),
                    "adhoc": gl.get("adhoc", False),
                    "gene_count": int(gl.get("gene_count") or 0),
                }
                for gl in isgls
            ]
        }

    def effective_genes_payload(self, *, sample: dict) -> dict[str, Any]:
        """Return the effective gene set for a sample.

        Args:
            sample: Sample payload used to resolve active filters.

        Returns:
            dict[str, Any]: Effective genes and panel coverage counts.
        """
        filters = sample.get("filters", {})
        assay = sample.get("assay")
        if not assay:
            raise api_error(400, "Sample is missing the 'assay' field")
        asp = self.assay_panel_handler.get_asp(assay)
        asp_group = asp.get("asp_group")
        asp_covered_genes, _asp_germline_genes = self.assay_panel_handler.get_asp_genes(assay)

        effective_genes = set(asp_covered_genes)
        adhoc_genes = set(filters.get("adhoc_genes", {}).get("genes", []))
        isgl_genes: set[str] = set()

        genelists = filters.get("genelists", [])
        if genelists:
            isgls = self.gene_list_handler.get_isgl_by_ids(genelists)
            for _gl_key, gl_values in isgls.items():
                isgl_genes.update(gl_values.get("genes", []))

        filter_genes = adhoc_genes.union(isgl_genes) if adhoc_genes or isgl_genes else set()
        if filter_genes and asp_group not in ["tumwgs", "wts"]:
            effective_genes = effective_genes.intersection(filter_genes)
        elif filter_genes:
            effective_genes = deepcopy(filter_genes)

        items = sorted(effective_genes)
        return {"items": items, "asp_covered_genes_count": len(asp_covered_genes)}

    def edit_context_payload(self, *, sample: dict) -> dict[str, Any]:
        """Return edit-context data for a sample.

        Args:
            sample: Sample payload being edited.

        Returns:
            dict[str, Any]: Sample, panel, and variant-stat context.
        """
        assay = sample.get("assay")
        if not assay:
            raise api_error(400, "Sample is missing the 'assay' field")
        asp = self.assay_panel_handler.get_asp(assay)
        asp_group = asp.get("asp_group")

        if sample.get("filters") is None:
            assay_config = get_formatted_assay_config(sample)
            self.sample_handler.reset_sample_settings(
                sample.get("_id"), assay_config.get("filters")
            )
            sample = self.sample_handler.get_sample(sample["_id"])

        filters = sample.get("filters", {})
        assay = sample.get("assay")
        asp_covered_genes, _asp_germline_genes = self.assay_panel_handler.get_asp_genes(assay)
        effective_genes = set(asp_covered_genes)

        adhoc_genes = set(filters.get("adhoc_genes", {}).get("genes", []))
        isgl_genes: set[str] = set()
        genelists = filters.get("genelists", [])
        if genelists:
            isgls = self.gene_list_handler.get_isgl_by_ids(genelists)
            for _gl_key, gl_values in isgls.items():
                isgl_genes.update(gl_values.get("genes", []))
        filter_genes = adhoc_genes.union(isgl_genes) if adhoc_genes or isgl_genes else set()

        if filter_genes and asp_group not in ["tumwgs", "wts"]:
            effective_genes = effective_genes.intersection(filter_genes)
        elif filter_genes:
            effective_genes = deepcopy(filter_genes)
        effective_genes = sorted(effective_genes)

        variant_stats_raw = self.variant_handler.get_variant_stats(str(sample.get("_id")))
        if (
            effective_genes
            and variant_stats_raw
            and (len(effective_genes) < len(asp_covered_genes) or asp_group in ["tumwgs", "wts"])
        ):
            variant_stats_filtered = self.variant_handler.get_variant_stats(
                str(sample.get("_id")), genes=effective_genes
            )
        else:
            variant_stats_filtered = deepcopy(variant_stats_raw)

        return {
            "sample": sample,
            "asp": asp,
            "variant_stats_raw": variant_stats_raw,
            "variant_stats_filtered": variant_stats_filtered,
        }

    def apply_genelists(
        self, *, sample: dict, payload: dict[str, Any], sample_id: str
    ) -> dict[str, Any]:
        """Persist selected genelists for a sample.

        Args:
            sample: Sample payload being updated.
            payload: Request payload containing selected genelist IDs.
            sample_id: Sample identifier reported in the response.

        Returns:
            dict[str, Any]: Mutation response payload.
        """
        filters = sample.get("filters", {})
        genelist_ids = payload.get("isgl_ids", [])
        if not isinstance(genelist_ids, list):
            raise api_error(400, "Invalid isgl_ids payload")
        filters["genelists"] = list(deepcopy(genelist_ids))
        self.sample_handler.update_sample_filters(sample.get("_id"), filters)
        return {
            "status": "ok",
            "sample_id": sample_id,
            "action": "apply_genelists",
            "genelist_ids": genelist_ids,
        }

    def save_adhoc_genes(
        self, *, sample: dict, payload: dict[str, Any], sample_id: str
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

        filters = sample.get("filters", {})
        filters["adhoc_genes"] = {"label": label, "genes": genes}
        self.sample_handler.update_sample_filters(sample.get("_id"), filters)
        return {
            "status": "ok",
            "sample_id": sample_id,
            "action": "save_adhoc_genes",
            "label": label,
            "gene_count": len(genes),
        }

    def clear_adhoc_genes(self, *, sample: dict, sample_id: str) -> dict[str, Any]:
        """Remove ad hoc genes from a sample filter set.

        Args:
            sample: Sample payload being updated.
            sample_id: Sample identifier reported in the response.

        Returns:
            dict[str, Any]: Mutation response payload.
        """
        filters = sample.get("filters", {})
        filters.pop("adhoc_genes", None)
        self.sample_handler.update_sample_filters(sample.get("_id"), filters)
        return {"status": "ok", "sample_id": sample_id, "action": "clear_adhoc_genes"}

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
        report = self.sample_handler.get_report(sample_id, report_id)
        report_name = report.get("report_name")
        filepath = report.get("filepath")

        if not filepath and report_name:
            assay_config = get_formatted_assay_config(sample)
            report_sub_dir = assay_config.get("reporting", {}).get("report_path", "")
            filepath = (
                f"{runtime_app.config.get('REPORTS_BASE_PATH', '')}/{report_sub_dir}/{report_name}"
            )

        return {
            "sample_id": sample_id,
            "report_id": report_id,
            "report_name": report_name,
            "filepath": filepath,
        }

    def add_sample_comment(self, *, sample_id: str, doc: dict[str, Any]) -> None:
        """Persist a sample comment."""
        self.sample_handler.add_sample_comment(sample_id, doc)

    def set_sample_comment_hidden(self, *, sample_id: str, comment_id: str, hidden: bool) -> None:
        """Hide or unhide a sample comment."""
        if hidden:
            self.sample_handler.hide_sample_comment(sample_id, comment_id)
            return
        self.sample_handler.unhide_sample_comment(sample_id, comment_id)

    def replace_sample_filters(self, *, sample: dict, filters: dict[str, Any]) -> None:
        """Replace the stored filters for a sample."""
        self.sample_handler.update_sample_filters(sample.get("_id"), filters)

    def reset_sample_filters(self, *, sample: dict, assay_config: dict) -> None:
        """Reset a sample's filters from assay defaults."""
        self.sample_handler.reset_sample_settings(sample.get("_id"), assay_config.get("filters"))

    def add_coverage_blacklist(
        self, *, gene: str, coord: str | None, region: str, smp_grp: str
    ) -> None:
        """Create a coverage blacklist entry."""
        if coord:
            sanitized_coord = str(coord).replace(":", "_").replace("-", "_")
            self.grouped_coverage_handler.blacklist_coord(gene, sanitized_coord, region, smp_grp)
            return
        self.grouped_coverage_handler.blacklist_gene(gene, smp_grp)

    def remove_coverage_blacklist(self, *, obj_id: str) -> None:
        """Delete a coverage blacklist entry."""
        self.grouped_coverage_handler.remove_blacklist(obj_id)


__all__ = ["SampleCatalogService"]
