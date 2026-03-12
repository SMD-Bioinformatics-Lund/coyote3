"""Sample catalog and sample workflow service."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from api.core.home.ports import HomeRepository
from api.http import api_error, get_formatted_assay_config
from api.repositories.home_repository import HomeRepository as MongoHomeRepository
from api.runtime import app as runtime_app


class SampleCatalogService:
    def __init__(self, repository: HomeRepository | None = None) -> None:
        self.repository = repository or MongoHomeRepository()

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

        done_samples = self.repository.get_samples(
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
        if not search_applied and len(done_samples) > per_done_page:
            has_next_done = True
            done_samples = done_samples[:per_done_page]

        live_samples = self.repository.get_samples(
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
        query = {"asp_name": sample.get("assay"), "is_active": True}
        isgls = self.repository.get_isgl_by_asp(**query)
        return {
            "items": [
                {
                    "_id": str(gl["_id"]),
                    "name": gl["displayname"],
                    "version": gl.get("version"),
                    "adhoc": gl.get("adhoc", False),
                    "gene_count": int(gl.get("gene_count") or 0),
                }
                for gl in isgls
            ]
        }

    def effective_genes_payload(self, *, sample: dict) -> dict[str, Any]:
        filters = sample.get("filters", {})
        assay = sample.get("assay")
        asp = self.repository.get_asp(assay)
        asp_group = asp.get("asp_group")
        asp_covered_genes, _asp_germline_genes = self.repository.get_asp_genes(assay)

        effective_genes = set(asp_covered_genes)
        adhoc_genes = set(filters.get("adhoc_genes", {}).get("genes", []))
        isgl_genes: set[str] = set()

        genelists = filters.get("genelists", [])
        if genelists:
            isgls = self.repository.get_isgl_by_ids(genelists)
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
        asp = self.repository.get_asp(sample.get("assay"))
        asp_group = asp.get("asp_group")

        if sample.get("filters") is None:
            assay_config = get_formatted_assay_config(sample)
            self.repository.reset_sample_settings(sample.get("_id"), assay_config.get("filters"))
            sample = self.repository.get_sample(sample["_id"])

        filters = sample.get("filters", {})
        assay = sample.get("assay")
        asp_covered_genes, _asp_germline_genes = self.repository.get_asp_genes(assay)
        effective_genes = set(asp_covered_genes)

        adhoc_genes = set(filters.get("adhoc_genes", {}).get("genes", []))
        isgl_genes: set[str] = set()
        genelists = filters.get("genelists", [])
        if genelists:
            isgls = self.repository.get_isgl_by_ids(genelists)
            for _gl_key, gl_values in isgls.items():
                isgl_genes.update(gl_values.get("genes", []))
        filter_genes = adhoc_genes.union(isgl_genes) if adhoc_genes or isgl_genes else set()

        if filter_genes and asp_group not in ["tumwgs", "wts"]:
            effective_genes = effective_genes.intersection(filter_genes)
        elif filter_genes:
            effective_genes = deepcopy(filter_genes)
        effective_genes = sorted(effective_genes)

        variant_stats_raw = self.repository.get_variant_stats(str(sample.get("_id")))
        if effective_genes and variant_stats_raw and (
            len(effective_genes) < len(asp_covered_genes) or asp_group in ["tumwgs", "wts"]
        ):
            variant_stats_filtered = self.repository.get_variant_stats(str(sample.get("_id")), genes=effective_genes)
        else:
            variant_stats_filtered = deepcopy(variant_stats_raw)

        return {
            "sample": sample,
            "asp": asp,
            "variant_stats_raw": variant_stats_raw,
            "variant_stats_filtered": variant_stats_filtered,
        }

    def apply_genelists(self, *, sample: dict, payload: dict[str, Any], sample_id: str) -> dict[str, Any]:
        filters = sample.get("filters", {})
        genelist_ids = payload.get("isgl_ids", [])
        if not isinstance(genelist_ids, list):
            raise api_error(400, "Invalid isgl_ids payload")
        filters["genelists"] = list(deepcopy(genelist_ids))
        self.repository.update_sample_filters(sample.get("_id"), filters)
        return {"status": "ok", "sample_id": sample_id, "action": "apply_genelists", "genelist_ids": genelist_ids}

    def save_adhoc_genes(self, *, sample: dict, payload: dict[str, Any], sample_id: str) -> dict[str, Any]:
        genes_raw = payload.get("genes", "")
        genes = [g.strip() for g in re.split(r"[ ,\n]+", genes_raw) if g.strip()]
        genes.sort()
        label = payload.get("label") or "adhoc"

        filters = sample.get("filters", {})
        filters["adhoc_genes"] = {"label": label, "genes": genes}
        self.repository.update_sample_filters(sample.get("_id"), filters)
        return {
            "status": "ok",
            "sample_id": sample_id,
            "action": "save_adhoc_genes",
            "label": label,
            "gene_count": len(genes),
        }

    def clear_adhoc_genes(self, *, sample: dict, sample_id: str) -> dict[str, Any]:
        filters = sample.get("filters", {})
        filters.pop("adhoc_genes", None)
        self.repository.update_sample_filters(sample.get("_id"), filters)
        return {"status": "ok", "sample_id": sample_id, "action": "clear_adhoc_genes"}

    def report_context_payload(self, *, sample: dict, report_id: str, sample_id: str) -> dict[str, Any]:
        report = self.repository.get_report(sample_id, report_id)
        report_name = report.get("report_name")
        filepath = report.get("filepath")

        if not filepath and report_name:
            assay_config = get_formatted_assay_config(sample)
            report_sub_dir = assay_config.get("reporting", {}).get("report_folder", "")
            filepath = f"{runtime_app.config.get('REPORTS_BASE_PATH', '')}/{report_sub_dir}/{report_name}"

        return {
            "sample_id": sample_id,
            "report_id": report_id,
            "report_name": report_name,
            "filepath": filepath,
        }


__all__ = ["SampleCatalogService"]
