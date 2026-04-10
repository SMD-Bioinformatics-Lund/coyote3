"""Sample catalog and sample workflow service."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from api.http import api_error, get_formatted_assay_config
from api.runtime_state import app as runtime_app

FILE_DISPLAY_METADATA: dict[str, dict[str, str]] = {
    "vcf_files": {
        "label": "VCF",
        "icon": "document-text",
        "missing_msg": "No VCF file available",
    },
    "cnv": {
        "label": "CNV JSON",
        "icon": "clipboard-document-list",
        "missing_msg": "No CNV JSON available",
    },
    "transloc": {
        "label": "Transloc VCF",
        "icon": "link",
        "missing_msg": "No Transloc VCF available",
    },
    "cov": {
        "label": "Coverage JSON",
        "icon": "chart-bar",
        "missing_msg": "No coverage file available",
    },
    "biomarkers": {
        "label": "Biomarkers JSON",
        "icon": "finger-print",
        "missing_msg": "No biomarkers file available",
    },
    "cnvprofile": {
        "label": "CNV Profile (image)",
        "icon": "photo",
        "missing_msg": "No CNV profile available",
    },
    "fusion_files": {
        "label": "Fusion Calls",
        "icon": "link",
        "missing_msg": "No fusion file available",
    },
    "expression_path": {
        "label": "Expression",
        "icon": "clipboard-document-list",
        "missing_msg": "No Expression file available",
    },
    "classification_path": {
        "label": "Classification",
        "icon": "document-text",
        "missing_msg": "No Classification file available",
    },
    "qc": {
        "label": "QC",
        "icon": "chart-bar",
        "missing_msg": "No QC file available",
    },
}

FILE_COUNT_BADGE_METADATA: dict[str, tuple[str, str]] = {
    "vcf_files": ("snvs", "SNVs"),
    "cnv": ("cnvs", "CNVs"),
    "transloc": ("transloc", "Translocs"),
    "fusion_files": ("fusions", "Fusions"),
    "expression_path": ("rna_expr", "Expr"),
    "classification_path": ("rna_class", "classes"),
    "qc": ("qc", "data"),
}


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
            copy_number_variant_handler=store.copy_number_variant_handler,
            fusion_handler=store.fusion_handler,
            translocation_handler=store.translocation_handler,
            biomarker_handler=store.biomarker_handler,
            grouped_coverage_handler=store.grouped_coverage_handler,
        )

    def __init__(
        self,
        *,
        sample_handler: Any,
        gene_list_handler: Any,
        assay_panel_handler: Any,
        variant_handler: Any,
        copy_number_variant_handler: Any,
        fusion_handler: Any,
        translocation_handler: Any,
        biomarker_handler: Any,
        grouped_coverage_handler: Any,
    ) -> None:
        """Create the service with explicit injected handlers."""
        self.sample_handler = sample_handler
        self.gene_list_handler = gene_list_handler
        self.assay_panel_handler = assay_panel_handler
        self.variant_handler = variant_handler
        self.copy_number_variant_handler = copy_number_variant_handler
        self.fusion_handler = fusion_handler
        self.translocation_handler = translocation_handler
        self.biomarker_handler = biomarker_handler
        self.grouped_coverage_handler = grouped_coverage_handler

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

    @classmethod
    def _file_rows_for_sample(
        cls, sample: dict[str, Any], asp: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Build Files & QC rows from assay-configured expected file keys."""
        data_counts = dict(sample.get("data_counts") or {})
        rows: list[dict[str, Any]] = []
        for key in cls._expected_file_keys_for_sample(sample, asp):
            meta = FILE_DISPLAY_METADATA.get(key)
            if not meta:
                continue
            path = sample.get(key)
            count_key, count_suffix = FILE_COUNT_BADGE_METADATA.get(key, ("", ""))
            count_badge = None
            if count_key and data_counts.get(count_key):
                count_badge = f"{data_counts[count_key]} {count_suffix}"
            elif key in {"cov", "biomarkers"} and data_counts.get(key):
                count_badge = "Loaded"
            rows.append(
                {
                    "key": key,
                    "label": meta["label"],
                    "path": path,
                    "present": bool(path),
                    "icon": meta["icon"],
                    "missing_msg": meta["missing_msg"],
                    "count_badge": count_badge,
                }
            )
        return rows

    @staticmethod
    def _normalize_list_target(sample: dict, target: str | None) -> str:
        """Normalize a list/effective-gene target for the sample's omics layer."""
        omics = str(sample.get("omics_layer", "")).strip().lower()
        if target is None or not isinstance(target, str):
            normalized = ""
        else:
            normalized = target.strip().lower()
        if omics == "rna":
            return normalized if normalized in {"fusion", "all"} else "fusion"
        return normalized if normalized in {"snv", "cnv", "all"} else "snv"

    @staticmethod
    def _filter_key_for_target(target: str) -> str:
        """Map a target scope to the canonical stored filter-list key."""
        return {
            "snv": "genelists",
            "cnv": "cnv_genelists",
            "fusion": "fusionlists",
        }.get(target, "genelists")

    @staticmethod
    def _normalized_gl_list_types(gl: dict[str, Any]) -> set[str]:
        """Return a normalized set of supported list types for an ISGL document."""
        raw = gl.get("list_type") or []
        if isinstance(raw, str):
            values = {raw.strip().lower()}
        else:
            values = {str(value).strip().lower() for value in raw if str(value).strip()}
        normalized: set[str] = set()
        if {"small_variant_genelist"} & values:
            normalized.add("snv")
        if {"cnv_genelist"} & values:
            normalized.add("cnv")
        if {"fusion_genelist"} & values:
            normalized.add("fusion")
        if not normalized:
            normalized.add("snv")
        return normalized

    @classmethod
    def _is_matching_target(cls, gl: dict[str, Any], target: str) -> bool:
        """Check whether a genelist document matches the requested scope."""
        supported_targets = cls._normalized_gl_list_types(gl)
        return target == "all" or target in supported_targets

    @classmethod
    def _normalized_adhoc_genes(cls, filters: dict[str, Any]) -> dict[str, Any] | None:
        """Normalize ad hoc gene filter shapes into a scope-keyed structure."""
        raw = filters.get("adhoc_genes")
        if not raw:
            return None
        if isinstance(raw, dict):
            scoped_keys = {"snv", "cnv", "fusion", "all"}
            if scoped_keys & set(raw.keys()):
                normalized_scopes: dict[str, Any] = {}
                for scope in scoped_keys:
                    entry = raw.get(scope)
                    if not isinstance(entry, dict):
                        continue
                    genes = [str(g).strip() for g in entry.get("genes", []) if str(g).strip()]
                    label = str(entry.get("label") or "adhoc").strip() or "adhoc"
                    if genes:
                        normalized_scopes[scope] = {"label": label, "genes": sorted(set(genes))}
                return normalized_scopes or None

            genes = [str(g).strip() for g in raw.get("genes", []) if str(g).strip()]
            list_types = raw.get("list_types")
            if isinstance(list_types, str):
                normalized_types = [list_types.strip().lower()] if list_types.strip() else ["snv"]
            elif isinstance(list_types, list):
                normalized_types = [
                    str(value).strip().lower() for value in list_types if str(value).strip()
                ]
            else:
                normalized_types = ["snv"]
            normalized_types = list(dict.fromkeys(normalized_types or ["snv"]))
            normalized_scopes = {}
            for scope in normalized_types:
                if scope not in scoped_keys:
                    continue
                normalized_scopes[scope] = {
                    "label": str(raw.get("label") or "adhoc").strip() or "adhoc",
                    "genes": sorted(set(genes)),
                }
            return normalized_scopes or None
        if isinstance(raw, list):
            genes = [str(g).strip() for g in raw if str(g).strip()]
            if genes:
                return {"snv": {"label": "adhoc", "genes": sorted(set(genes))}}
        return None

    @classmethod
    def _adhoc_genes_for_target(cls, filters: dict[str, Any], target: str) -> set[str]:
        """Return ad hoc genes that apply to the requested scope."""
        adhoc = cls._normalized_adhoc_genes(filters)
        if not adhoc:
            return set()
        genes: set[str] = set()
        if target == "all":
            for entry in adhoc.values():
                genes.update(entry.get("genes", []))
            return genes
        for scope in ("all", target):
            entry = adhoc.get(scope)
            if isinstance(entry, dict):
                genes.update(entry.get("genes", []))
        return genes

    @staticmethod
    def _count_items(rows: Any) -> int:
        """Return a safe count for handler results that may be list-like or cursors."""
        if rows is None:
            return 0
        if isinstance(rows, list):
            return len(rows)
        try:
            return len(list(rows))
        except Exception:
            return 0

    @staticmethod
    def _collect_doc_gene_names(doc: dict[str, Any]) -> set[str]:
        """Collect gene-like names from heterogenous DNA/RNA result documents."""
        genes: set[str] = set()

        def _add(value: Any) -> None:
            text = str(value or "").strip()
            if text:
                genes.add(text)

        for key in ("gene", "gene1", "gene2"):
            _add(doc.get(key))

        gene_blob = str(doc.get("genes") or "").strip()
        if gene_blob:
            for piece in re.split(r"[^A-Za-z0-9_]+", gene_blob):
                _add(piece)

        for gene_doc in doc.get("genes", []) or []:
            if isinstance(gene_doc, dict):
                _add(gene_doc.get("gene"))

        info = doc.get("INFO")
        if isinstance(info, list):
            info_entries = info
        elif isinstance(info, dict):
            info_entries = [info]
        else:
            info_entries = []

        for entry in info_entries:
            anns = entry.get("ANN") if isinstance(entry, dict) else None
            for ann in anns or []:
                if not isinstance(ann, dict):
                    continue
                gene_name = ann.get("Gene_Name")
                if isinstance(gene_name, str):
                    for piece in gene_name.split("&"):
                        _add(piece)
        return genes

    @classmethod
    def _count_matching_docs(cls, rows: Any, genes: set[str]) -> int:
        """Count docs whose resolved gene names intersect the provided gene set."""
        if not genes:
            return 0
        total = 0
        for row in rows or []:
            if isinstance(row, dict) and cls._collect_doc_gene_names(row) & genes:
                total += 1
        return total

    def _effective_genes_for_target(
        self, *, sample: dict, asp: dict[str, Any], target: str
    ) -> tuple[list[str], list[str], str]:
        """Resolve effective genes for a target scope plus panel metadata."""
        filters = sample.get("filters", {})
        assay = sample.get("assay")
        if not assay:
            raise api_error(400, "Sample is missing the 'assay' field")
        asp_group = str(asp.get("asp_group") or "")
        asp_covered_genes, _asp_germline_genes = self.assay_panel_handler.get_asp_genes(assay)

        effective_genes = set(asp_covered_genes)
        adhoc_genes = self._adhoc_genes_for_target(filters, target)
        isgl_genes: set[str] = set()

        selected_list_ids = filters.get(self._filter_key_for_target(target), [])
        if selected_list_ids:
            isgls = self.gene_list_handler.get_isgl_by_ids(selected_list_ids)
            for _gl_key, gl_values in isgls.items():
                isgl_genes.update(gl_values.get("genes", []))

        filter_genes = adhoc_genes.union(isgl_genes) if adhoc_genes or isgl_genes else set()
        if filter_genes and asp_group not in ["tumwgs", "wts"]:
            effective_genes = effective_genes.intersection(filter_genes)
        elif filter_genes:
            effective_genes = deepcopy(filter_genes)
        return sorted(effective_genes), asp_covered_genes, asp_group

    def _analysis_counts(
        self, *, sample: dict, asp: dict[str, Any], variant_stats_raw: dict[str, Any]
    ) -> tuple[dict[str, int], dict[str, int], dict[str, Any]]:
        """Return raw/filtered analysis-type counts plus SNV stats."""
        sample_id = str(sample.get("_id"))
        snv_genes, asp_covered_genes, asp_group = self._effective_genes_for_target(
            sample=sample, asp=asp, target="snv"
        )
        cnv_genes, _cnv_covered_genes, _ = self._effective_genes_for_target(
            sample=sample, asp=asp, target="cnv"
        )
        fusion_genes, _fusion_covered_genes, _ = self._effective_genes_for_target(
            sample=sample, asp=asp, target="fusion"
        )

        variant_stats_filtered = deepcopy(variant_stats_raw or {})
        if (
            snv_genes
            and variant_stats_raw
            and (len(snv_genes) < len(asp_covered_genes) or asp_group in ["tumwgs", "wts"])
        ):
            variant_stats_filtered = self.variant_handler.get_variant_stats(
                sample_id, genes=snv_genes
            )

        cnv_rows = list(
            self.copy_number_variant_handler.get_sample_cnvs({"SAMPLE_ID": sample_id}) or []
        )
        transloc_rows = list(self.translocation_handler.get_sample_translocations(sample_id) or [])
        fusion_rows = list(self.fusion_handler.get_sample_fusions({"SAMPLE_ID": sample_id}) or [])
        biomarker_rows = list(self.biomarker_handler.get_sample_biomarkers(sample_id) or [])

        raw_counts = {
            "snv": int(variant_stats_raw.get("variants") or 0),
            "cnv": self._count_items(cnv_rows),
            "transloc": self._count_items(transloc_rows),
            "fusion": self._count_items(fusion_rows),
            "biomarker": self._count_items(biomarker_rows),
        }
        filtered_counts = {
            "snv": int(variant_stats_filtered.get("variants") or 0),
            "cnv": self._count_matching_docs(cnv_rows, set(cnv_genes))
            if cnv_genes
            else raw_counts["cnv"],
            "transloc": self._count_matching_docs(transloc_rows, set(snv_genes))
            if snv_genes
            else raw_counts["transloc"],
            "fusion": self._count_matching_docs(fusion_rows, set(fusion_genes))
            if fusion_genes
            else raw_counts["fusion"],
            "biomarker": raw_counts["biomarker"],
        }
        return raw_counts, filtered_counts, variant_stats_filtered

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

    def genelist_items_payload(self, *, sample: dict, target: str | None = None) -> dict[str, Any]:
        """Return selectable genelist items for a sample.

        Args:
            sample: Sample payload used to resolve active genelists.

        Returns:
            dict[str, Any]: Genelist item payload for the UI.
        """
        target = self._normalize_list_target(sample, target)
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
                    "list_types": sorted(self._normalized_gl_list_types(gl)),
                }
                for gl in isgls
                if self._is_matching_target(gl, target)
            ]
        }

    def effective_genes_payload(self, *, sample: dict, target: str | None = None) -> dict[str, Any]:
        """Return the effective gene set for a sample.

        Args:
            sample: Sample payload used to resolve active filters.

        Returns:
            dict[str, Any]: Effective genes and panel coverage counts.
        """
        target = self._normalize_list_target(sample, target)
        assay = sample.get("assay")
        if not assay:
            raise api_error(400, "Sample is missing the 'assay' field")
        asp = self.assay_panel_handler.get_asp(assay)
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
        assay = sample.get("assay")
        if not assay:
            raise api_error(400, "Sample is missing the 'assay' field")
        asp = self.assay_panel_handler.get_asp(assay)

        if sample.get("filters") is None:
            assay_config = get_formatted_assay_config(sample)
            self.sample_handler.reset_sample_settings(
                sample.get("_id"), assay_config.get("filters")
            )
            sample = self.sample_handler.get_sample(sample["_id"])

        filters = sample.get("filters", {})
        adhoc_scopes = self._normalized_adhoc_genes(filters) or {}

        sample = deepcopy(sample)
        sample_filters = dict(sample.get("filters", {}) or {})
        sample_filters["adhoc_genes"] = adhoc_scopes
        sample["filters"] = sample_filters

        variant_stats_raw = self.variant_handler.get_variant_stats(str(sample.get("_id")))
        analysis_counts_raw, analysis_counts_filtered, variant_stats_filtered = (
            self._analysis_counts(
                sample=sample,
                asp=asp,
                variant_stats_raw=variant_stats_raw,
            )
        )

        return {
            "sample": sample,
            "asp": asp,
            "sample_expected_files": self._file_rows_for_sample(sample, asp),
            "analysis_counts_raw": analysis_counts_raw,
            "analysis_counts_filtered": analysis_counts_filtered,
            "variant_stats_raw": variant_stats_raw,
            "variant_stats_filtered": variant_stats_filtered,
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
        filters = dict(sample.get("filters", {}) or {})
        genelist_ids = payload.get("isgl_ids", [])
        if not isinstance(genelist_ids, list):
            raise api_error(400, "Invalid isgl_ids payload")
        filters[self._filter_key_for_target(target)] = list(deepcopy(genelist_ids))
        self.sample_handler.update_sample_filters(sample.get("_id"), filters)
        return {
            "status": "ok",
            "sample_id": sample_id,
            "action": "apply_genelists",
            "genelist_ids": genelist_ids,
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
        filters = dict(sample.get("filters", {}) or {})
        adhoc_scopes = self._normalized_adhoc_genes(filters) or {}
        adhoc_scopes[target] = {
            "label": label,
            "genes": genes,
        }
        filters["adhoc_genes"] = adhoc_scopes
        self.sample_handler.update_sample_filters(sample.get("_id"), filters)
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
        filters = dict(sample.get("filters", {}) or {})
        requested_target = target if isinstance(target, str) and target.strip() else None
        target = self._normalize_list_target(sample, requested_target)
        adhoc_scopes = self._normalized_adhoc_genes(filters)
        if not adhoc_scopes:
            return {"status": "ok", "sample_id": sample_id, "action": "clear_adhoc_genes"}
        if target == "all":
            adhoc_scopes.pop("all", None)
        else:
            adhoc_scopes.pop(target, None)
        if adhoc_scopes:
            filters["adhoc_genes"] = adhoc_scopes
        else:
            filters.pop("adhoc_genes", None)
        self.sample_handler.update_sample_filters(sample.get("_id"), filters)
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
