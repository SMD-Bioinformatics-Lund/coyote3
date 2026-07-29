"""Sample catalog and sample workflow service."""

from __future__ import annotations

import os
import re
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from api.application.common.assay_config import get_formatted_assay_config
from api.config.constants import DEFAULT_ENVIRONMENT, primary_analysis_file_key
from api.domain.common.assay_filters import get_sample_effective_genes
from api.domain.common.errors import api_error
from api.domain.common.sample_filters import (
    merge_filter_defaults,
    normalize_sample_filters,
    sample_filters_from_aspc_filters,
)

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


class SampleCatalogService:
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
            "snv": "snvlists",
            "cnv": "cnvlists",
            "fusion": "fusionlists",
        }.get(target, "snvlists")

    @staticmethod
    def _filter_section_for_target(target: str) -> str:
        """Map target scope to the sample filter section."""
        return "fusion" if target == "fusion" else target

    @classmethod
    def _sample_filters(cls, sample: dict[str, Any]) -> dict[str, Any]:
        """Return the complete persisted filter profile map."""
        return normalize_sample_filters(
            sample.get("filters"),
            omics_layer=str(sample.get("omics_layer") or "dna"),
            analysis_intents=sample.get("analysis_intents"),
            canonical=True,
        )

    @classmethod
    def _target_filters(cls, sample: dict[str, Any], target: str) -> dict[str, Any]:
        """Return the mutable filter section for a target."""
        filters = cls._sample_filters(sample)
        section = cls._filter_section_for_target(target)
        section_filters = (filters.get("somatic") or {}).get(section)
        return deepcopy(section_filters) if isinstance(section_filters, dict) else {}

    @classmethod
    def _replace_target_filters(
        cls, sample: dict[str, Any], target: str, target_filters: dict[str, Any]
    ) -> dict[str, Any]:
        """Return full sample filters with one target section replaced."""
        filters = cls._sample_filters(sample)
        filters.setdefault("somatic", {})[cls._filter_section_for_target(target)] = deepcopy(
            target_filters
        )
        return filters

    @staticmethod
    def _normalized_gl_list_types(gl: dict[str, Any]) -> set[str]:
        """Return a normalized set of supported list types for an ISGL document."""
        raw = gl.get("list_type") or []
        if isinstance(raw, str):
            values = {raw.strip().lower()}
        else:
            values = {str(value).strip().lower() for value in raw if str(value).strip()}
        normalized: set[str] = set()
        if {"snv", "adhoc_snv"} & values:
            normalized.add("snv")
        if {"cnv", "adhoc_cnv"} & values:
            normalized.add("cnv")
        if {"fusion", "adhoc_fusion"} & values:
            normalized.add("fusion")
        if {"expression", "adhoc_expression"} & values:
            normalized.add("expression")
        if {"pgx", "adhoc_pgx"} & values:
            normalized.add("pgx")
        if not normalized:
            normalized.add("snv")
        return normalized

    @classmethod
    def _is_matching_target(cls, gl: dict[str, Any], target: str) -> bool:
        """Check whether a genelist document matches the requested scope."""
        supported_targets = cls._normalized_gl_list_types(gl)
        return target == "all" or target in supported_targets

    @staticmethod
    def _isgl_list_type_for_target(target: str) -> str | None:
        """Map UI target names to ISGL list_type values."""
        return {
            "snv": "snv",
            "cnv": "cnv",
            "fusion": "fusion",
        }.get(target)

    @classmethod
    def _genelist_option(cls, gl: dict[str, Any]) -> dict[str, Any]:
        """Return a compact, stable UI option for an ISGL document."""
        isgl_id = str(gl.get("isgl_id") or "")
        label = str(gl.get("displayname") or gl.get("name") or isgl_id)
        raw_list_type = gl.get("list_type") or []
        if isinstance(raw_list_type, str):
            list_type = [raw_list_type]
        else:
            list_type = list(raw_list_type)
        return {
            "id": isgl_id,
            "isgl_id": isgl_id,
            "name": label,
            "display_name": label,
            "version": gl.get("version"),
            "adhoc": gl.get("adhoc", False),
            "gene_count": int(gl.get("gene_count") or len(gl.get("genes") or []) or 0),
            "list_types": sorted(cls._normalized_gl_list_types(gl)),
            "list_type": list_type,
            "asp_ids": list(gl.get("asp_ids") or []),
            "asp_groups": list(gl.get("asp_groups") or []),
            "subpanel_id": gl.get("subpanel_id"),
            "diagnosis": gl.get("diagnosis"),
        }

    def _genelist_options_for_target(
        self, *, sample: dict[str, Any], asp: dict[str, Any], target: str
    ) -> list[dict[str, Any]]:
        """Return selectable ISGL options scoped by assay or assay group."""
        list_type = self._isgl_list_type_for_target(target)
        isgls = self.gene_list_repository.get_isgl_for_scope(
            asp_name=sample.get("asp_id"),
            assay_group=asp.get("asp_group"),
            is_active=True,
            adhoc=False,
            list_type=list_type,
        )
        return [self._genelist_option(gl) for gl in isgls if self._is_matching_target(gl, target)]

    def _selected_gene_panel_summary(
        self, *, sample: dict[str, Any], asp: dict[str, Any]
    ) -> dict[str, Any]:
        """Return selected ISGL/ad-hoc list summaries for the sample header card."""
        omics = str(sample.get("omics_layer") or "dna").strip().lower()
        targets = ["fusion"] if omics == "rna" else ["snv", "cnv"]
        summary: dict[str, Any] = {}
        for target in targets:
            target_filters = self._target_filters(sample, target)
            selected_ids = list(target_filters.get(self._filter_key_for_target(target), []) or [])
            selected_docs = self.gene_list_repository.get_isgl_by_ids(selected_ids)
            covered_map, effective_genes = get_sample_effective_genes(
                sample, asp, selected_docs, target=target
            )
            lists: list[dict[str, Any]] = []
            for list_id, raw in covered_map.items():
                genes = list(raw.get("genes") or [])
                covered = list(raw.get("covered") or [])
                uncovered = list(raw.get("uncovered") or [])
                lists.append(
                    {
                        "id": str(list_id),
                        "name": str(raw.get("displayname") or raw.get("name") or list_id),
                        "adhoc": bool(raw.get("adhoc")),
                        "is_active": bool(raw.get("is_active", True)),
                        "gene_count": len(genes),
                        "covered_count": len(covered),
                        "uncovered_count": len(uncovered),
                        "genes": genes,
                        "covered": covered,
                        "uncovered": uncovered,
                    }
                )
            summary[target] = {
                "selected_ids": selected_ids,
                "lists": lists,
                "list_count": len(lists),
                "effective_gene_count": len(effective_genes),
                "effective_genes": effective_genes,
            }
        return summary

    @classmethod
    def _normalized_adhoc_genes(cls, filters: dict[str, Any]) -> dict[str, Any] | None:
        """Normalize ad hoc gene filter shapes into a scope-keyed structure."""
        raw = filters.get("adhoc_genes")
        if not raw:
            sectioned_raw: dict[str, Any] = {}
            for scope in ("snv", "cnv", "fusion"):
                section = filters.get(scope)
                if isinstance(section, dict) and section.get("adhoc_genes"):
                    sectioned_raw[scope] = section.get("adhoc_genes")
            raw = sectioned_raw or None
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
        filters = self._sample_filters(sample)
        target_filters = self._target_filters(sample, target)
        assay = sample.get("asp_id")
        if not assay:
            raise api_error(400, "Sample is missing the 'asp_id' field")
        asp_group = str(asp.get("asp_group") or "")
        asp_covered_genes, _asp_germline_genes = self.assay_panel_repository.get_asp_genes(assay)

        effective_genes = set(asp_covered_genes)
        adhoc_genes = self._adhoc_genes_for_target(filters, target)
        isgl_genes: set[str] = set()

        selected_list_ids = target_filters.get(self._filter_key_for_target(target), [])
        if selected_list_ids:
            isgls = self.gene_list_repository.get_isgl_by_ids(selected_list_ids)
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
            variant_stats_filtered = self.variant_repository.get_variant_stats(
                sample_id, genes=snv_genes
            )

        cnv_rows = list(
            self.copy_number_variant_repository.get_sample_cnvs({"SAMPLE_ID": sample_id}) or []
        )
        transloc_rows = list(
            self.translocation_repository.get_sample_translocations(sample_id) or []
        )
        fusion_rows = list(
            self.fusion_repository.get_sample_fusions({"SAMPLE_ID": sample_id}) or []
        )
        biomarker_rows = list(self.biomarker_repository.get_sample_biomarkers(sample_id) or [])

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
            for scoped_target in ("snv", "cnv", "fusion"):
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
            default_filters = sample_filters_from_aspc_filters(
                assay_config.get("filters"), str(sample.get("omics_layer") or "dna")
            )
            self.sample_repository.reset_sample_settings(
                sample.get("_id"),
                default_filters,
                aspc={
                    "_id": assay_config.get("_id"),
                    "aspc_id": assay_config.get("aspc_id"),
                    "version": assay_config.get("version"),
                },
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
            if scope in {"snv", "cnv", "fusion"}:
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

        return {
            "sample": sample,
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
            "selected_gene_panels": self._selected_gene_panel_summary(sample=sample, asp=asp),
            "analysis_sections": analysis_sections,
            "analysis_counts_raw": analysis_counts_raw,
            "analysis_counts_filtered": analysis_counts_filtered,
            "variant_stats_raw": variant_stats_raw,
            "variant_stats_filtered": variant_stats_filtered,
            "biomarkers": biomarker_rows,
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
        target_filters[self._filter_key_for_target(target)] = list(deepcopy(genelist_ids))
        filters = self._replace_target_filters(sample, target, target_filters)
        self.sample_repository.update_sample_filters(sample.get("_id"), filters)
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

        return {
            "sample_id": sample_id,
            "report_id": report_id,
            "report_name": report_name,
            "filepath": filepath,
            "pdf_report_name": pdf_report_name,
            "pdf_filepath": pdf_filepath,
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
        self.sample_repository.update_sample_filters(sample.get("_id"), normalized)

    def reset_sample_filters(self, *, sample: dict, assay_config: dict) -> None:
        """Reset a sample's filters from assay defaults."""
        default_filters = sample_filters_from_aspc_filters(
            assay_config.get("filters"),
            str(sample.get("omics_layer") or "dna"),
            analysis_intents=sample.get("analysis_intents"),
        )
        self.sample_repository.reset_sample_settings(
            sample.get("_id"),
            default_filters,
            aspc={
                "_id": assay_config.get("_id"),
                "aspc_id": assay_config.get("aspc_id"),
                "version": assay_config.get("version"),
            },
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


__all__ = ["SampleCatalogService"]
