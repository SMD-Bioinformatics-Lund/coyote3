"""Gene-list, filter, and analysis-count policy for sample catalog workflows."""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from api.domain.common.assay_filters import get_sample_effective_genes, has_sample_gene_restriction
from api.domain.common.errors import api_error
from api.domain.common.sample_filters import normalize_sample_filters


class SampleCatalogFiltersMixin:
    """Provide target-aware filter and effective-gene behavior."""

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
        return normalized if normalized in {"snv", "cnv", "translocation", "all"} else "snv"

    @staticmethod
    def _filter_key_for_target(target: str) -> str:
        """Map a target scope to the canonical stored filter-list key."""
        return {
            "snv": "snvlists",
            "cnv": "cnvlists",
            "fusion": "fusionlists",
            "translocation": "fusionlists",
        }.get(target, "snvlists")

    @staticmethod
    def _filter_section_for_target(target: str) -> str:
        """Map target scope to the sample filter section."""
        return target

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
        normalized_target = "fusion" if target == "translocation" else target
        return normalized_target == "all" or normalized_target in supported_targets

    def _validated_genelist_ids(self, values: Any, *, target: str) -> list[str]:
        """Validate selected ISGL IDs against one analysis-specific list contract."""
        if not isinstance(values, list):
            raise api_error(400, f"{target.upper()} gene-list selection must be a list")
        normalized_ids = list(
            dict.fromkeys(str(value).strip() for value in values if str(value).strip())
        )
        selected_docs = self.gene_list_repository.get_isgl_by_ids(normalized_ids)
        missing_ids = [list_id for list_id in normalized_ids if list_id not in selected_docs]
        incompatible_ids = [
            list_id
            for list_id, list_doc in selected_docs.items()
            if not self._is_matching_target(list_doc, target)
        ]
        if missing_ids:
            raise api_error(400, f"Unknown or inactive gene list(s): {', '.join(missing_ids)}")
        if incompatible_ids:
            raise api_error(
                400,
                f"Gene list(s) do not support {target.upper()} analysis: "
                + ", ".join(incompatible_ids),
            )
        return normalized_ids

    def _validate_filter_genelists(self, filters: dict[str, Any]) -> dict[str, Any]:
        """Validate every persisted analysis-specific ISGL selection."""
        validated = deepcopy(filters)
        for intent, target, key in (
            ("somatic", "snv", "snvlists"),
            ("germline", "snv", "snvlists"),
            ("somatic", "cnv", "cnvlists"),
            ("somatic", "fusion", "fusionlists"),
            ("somatic", "translocation", "fusionlists"),
        ):
            section = (validated.get(intent) or {}).get(target) or {}
            if key in section:
                section[key] = self._validated_genelist_ids(section[key], target=target)
        return validated

    @staticmethod
    def _isgl_list_type_for_target(target: str) -> str | None:
        """Map UI target names to ISGL list_type values."""
        return {
            "snv": "snv",
            "cnv": "cnv",
            "fusion": "fusion",
            "translocation": "fusion",
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
        targets = ["fusion"] if omics == "rna" else ["snv", "cnv", "translocation"]
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
            for scope in ("snv", "cnv", "fusion", "translocation"):
                section = filters.get(scope)
                if isinstance(section, dict) and section.get("adhoc_genes"):
                    sectioned_raw[scope] = section.get("adhoc_genes")
            raw = sectioned_raw or None
        if not raw:
            return None
        if isinstance(raw, dict):
            scoped_keys = {"snv", "cnv", "fusion", "translocation", "all"}
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
            text = str(value or "").strip().upper()
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
            if not isinstance(entry, dict):
                continue
            annotations = []
            mane_annotation = entry.get("MANE_ANN")
            if isinstance(mane_annotation, dict):
                annotations.append(mane_annotation)
            annotations.extend(ann for ann in (entry.get("ANN") or []) if isinstance(ann, dict))
            for ann in annotations:
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
        genes = {str(gene).strip().upper() for gene in genes if str(gene).strip()}
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
        resolved_asp = {**asp, "covered_genes": asp_covered_genes}
        selected_list_ids = target_filters.get(self._filter_key_for_target(target), [])
        selected_lists = self.gene_list_repository.get_isgl_by_ids(selected_list_ids)
        _covered_map, effective_genes = get_sample_effective_genes(
            {**sample, "filters": filters},
            resolved_asp,
            selected_lists,
            target=target,
        )
        return effective_genes, asp_covered_genes, asp_group

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
        translocation_genes, _translocation_covered_genes, _ = self._effective_genes_for_target(
            sample=sample, asp=asp, target="translocation"
        )

        variant_stats_filtered = deepcopy(variant_stats_raw or {})
        snv_restricted = has_sample_gene_restriction(sample, asp, target="snv")
        cnv_restricted = has_sample_gene_restriction(sample, asp, target="cnv")
        fusion_restricted = has_sample_gene_restriction(sample, asp, target="fusion")
        if snv_restricted and not snv_genes:
            variant_stats_filtered = {**variant_stats_filtered, "variants": 0}
        elif (
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
            if cnv_restricted
            else raw_counts["cnv"],
            "transloc": self._count_matching_docs(transloc_rows, set(translocation_genes))
            if has_sample_gene_restriction(sample, asp, target="translocation")
            else raw_counts["transloc"],
            "fusion": self._count_matching_docs(fusion_rows, set(fusion_genes))
            if fusion_restricted
            else raw_counts["fusion"],
            "biomarker": raw_counts["biomarker"],
        }
        return raw_counts, filtered_counts, variant_stats_filtered
