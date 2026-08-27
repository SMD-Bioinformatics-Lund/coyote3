"""Gene-table and coverage-matrix composition for the public catalog."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from api.config.constants import SUBPANEL_BASE_ID
from api.infra.observability.operations import measured_operation


class PublicCatalogGeneViewsMixin:
    """Compose gene detail, list, and matrix projections for a public catalog service."""

    def _covered_genes(self, asp_id: Optional[str]) -> Tuple[List[str], List[str]]:
        """Return covered and germline genes for an assay panel.

        Args:
            asp_id: Assay-panel identifier.

        Returns:
            Tuple[List[str], List[str]]: Covered and germline gene symbols.
        """
        if not asp_id:
            return [], []
        genes, germline = self.assay_panel_repository.get_asp_genes(asp_id)
        return list(genes or []), list(germline or [])

    def resolve_gene_table(
        self, asp_id: Optional[str], isgl_key: Optional[str]
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, int]]:
        """Resolve the public gene table for a category or genelist.

        Args:
            asp_id: Assay-panel identifier.
            isgl_key: Optional genelist identifier or assay-panel key.

        Returns:
            Tuple[str, List[Dict[str, Any]], Dict[str, int]]: Table kind, rows, and summary counts.
        """
        covered, germline = self._covered_genes(asp_id)

        if isgl_key == asp_id:
            show = sorted(set(covered))
            rows_raw = (
                list(self.hgnc_repository.get_metadata_by_symbols(show) or []) if show else []
            )
            rows = self._merge_with_placeholders(show, rows_raw)
            return (
                "covered",
                rows,
                {
                    "total": len(show),
                    "isgl_total": len(show),
                    "covered_total": len(covered),
                    "germline_total": len(germline),
                },
            )

        if isgl_key:
            isgl = self.gene_list_repository.get_isgl(isgl_key) or {}
            isgl_genes = list(isgl.get("genes", []) or [])
            if covered:
                show = sorted(set(isgl_genes).intersection(set(covered)))
                mode = "overlap"
            else:
                show = sorted(set(isgl_genes))
                mode = "genelist"
            rows_raw = (
                list(self.hgnc_repository.get_metadata_by_symbols(show) or []) if show else []
            )
            rows = self._merge_with_placeholders(show, rows_raw)
            return (
                mode,
                rows,
                {
                    "total": len(show),
                    "isgl_total": len(isgl_genes),
                    "covered_total": len(covered),
                    "germline_total": len(germline),
                },
            )

        show = sorted(set(covered))
        rows_raw = list(self.hgnc_repository.get_metadata_by_symbols(show) or []) if show else []
        rows = self._merge_with_placeholders(show, rows_raw)
        return (
            "covered",
            rows,
            {
                "total": len(show),
                "covered_total": len(covered),
                "germline_total": len(germline),
            },
        )

    @staticmethod
    def _list_values(value: Any) -> list[str]:
        """Normalize scalar/list HGNC fields to strings."""
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if value:
            return [str(value).strip()]
        return []

    @classmethod
    def _row_symbols(cls, row: Dict[str, Any]) -> set[str]:
        """Return all symbols that should resolve to one HGNC row."""
        symbols = {
            str(row.get("hgnc_symbol") or row.get("symbol") or "").strip(),
        }
        symbols.update(cls._list_values(row.get("prev_symbol")))
        symbols.update(cls._list_values(row.get("alias_symbol")))
        return {symbol.upper() for symbol in symbols if symbol}

    @classmethod
    def _row_with_requested_symbol(
        cls, row: Dict[str, Any], requested_symbol: str
    ) -> Dict[str, Any]:
        """Attach panel-display and HGNC resolution metadata to a gene row."""
        requested = str(requested_symbol or "").strip()
        approved = str(row.get("hgnc_symbol") or row.get("symbol") or "").strip()
        prev = {symbol.upper() for symbol in cls._list_values(row.get("prev_symbol"))}
        aliases = {symbol.upper() for symbol in cls._list_values(row.get("alias_symbol"))}
        requested_upper = requested.upper()
        if approved and requested_upper == approved.upper():
            source = "approved_symbol"
        elif requested_upper in prev:
            source = "previous_symbol"
        elif requested_upper in aliases:
            source = "alias_symbol"
        else:
            source = "unresolved"
        return {
            **row,
            "display_symbol": requested or approved,
            "resolved_symbol": approved or requested,
            "hgnc_match_source": source,
            "symbol_changed": bool(approved and requested and approved.upper() != requested_upper),
        }

    @staticmethod
    def _hgnc_placeholder(symbol: str) -> Dict[str, Any]:
        """Return an explicit unresolved gene row without a fabricated HGNC ID.

        Args:
                symbol: Symbol.

        Returns:
                The  hgnc placeholder result.
        """
        cleaned = (symbol or "").strip()
        return {
            "_id": None,
            "hgnc_id": None,
            "hgnc_symbol": cleaned,
            "gene_name": "",
            "status": "Unresolved",
            "locus": "",
            "locus_sortable": "",
            "alias_symbol": [],
            "alias_name": [],
            "prev_symbol": [],
            "prev_name": [],
            "date_approved_reserved": None,
            "date_symbol_changed": None,
            "date_name_changed": None,
            "date_modified": None,
            "entrez_id": None,
            "ensembl_gene_id": None,
            "refseq_accession": [],
            "cosmic": [],
            "omim_id": [],
            "pseudogene_org": [],
            "imgt": None,
            "lncrnadb": None,
            "lncipedia": None,
            "ensembl_mane_select": "",
            "refseq_mane_select": "",
            "chromosome": "",
            "other_chromosome": None,
            "start": "",
            "end": "",
            "gene_gc_content": None,
            "gene_description": "",
            "ensembl_canonical": False,
            "gene_type": [],
            "refseq_mane_plus_clinical": [],
            "addtional_transcript_info": {},
            "symbol": cleaned,
            "display_symbol": cleaned,
            "resolved_symbol": cleaned,
            "hgnc_match_source": "unresolved",
            "symbol_changed": False,
        }

    @classmethod
    def _merge_with_placeholders(
        cls, symbols: List[str], rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Return one catalog row per requested symbol with HGNC resolution metadata.

        Args:
                symbols: Symbols.
                rows: Rows.

        Returns:
                The  merge with placeholders result.
        """
        by_symbol: dict[str, Dict[str, Any]] = {}
        for row in rows or []:
            for symbol in cls._row_symbols(row):
                by_symbol.setdefault(symbol, row)

        out_rows: List[Dict[str, Any]] = []
        seen_requested: set[str] = set()
        for symbol in symbols or []:
            requested = str(symbol or "").strip()
            if not requested:
                continue
            requested_upper = requested.upper()
            if requested_upper in seen_requested:
                continue
            seen_requested.add(requested_upper)
            resolved = by_symbol.get(requested_upper)
            out_rows.append(
                cls._row_with_requested_symbol(resolved, requested)
                if resolved
                else cls._hgnc_placeholder(requested)
            )

        return sorted(
            out_rows, key=lambda g: (g.get("display_symbol") or g.get("hgnc_symbol") or "").upper()
        )

    def apply_drug_info(
        self, genes: List[Dict[str, Any]], druglist_name: str | None = None
    ) -> List[Dict[str, Any]]:
        """Annotate genes with drug-target membership."""
        drug_genes = self.gene_list_repository.get_isgl(druglist_name) or {}
        drug_symbols = set(drug_genes.get("genes", [])) if drug_genes else set()
        for gene in genes:
            symbol = gene.get("hgnc_symbol") or gene.get("symbol") or ""
            gene["drug_target"] = symbol in drug_symbols
        return genes

    def genelist_view_context(
        self, genelist_id: str, assay: str | None = None
    ) -> dict[str, Any] | None:
        """Return public view context for a genelist."""
        genelist = self.gene_list_repository.get_isgl(genelist_id, is_active=True)
        if not genelist:
            return None

        selected_assay = assay
        all_genes = genelist.get("genes", [])
        asp_ids = genelist.get("asp_ids", [])

        filtered_genes = all_genes
        germline_genes: list[str] = []
        if selected_assay and selected_assay in asp_ids:
            panel = self.assay_panel_repository.get_asp(selected_assay)
            panel_genes = panel.get("covered_genes", []) if panel else []
            germline_genes = panel.get("germline_genes", []) if panel else []
            filtered_genes = (
                sorted(set(all_genes).intersection(panel_genes))
                if panel and panel.get("asp_family") not in ["WGS", "WTS"]
                else all_genes
            )

        return {
            "genelist": genelist,
            "selected_assay": selected_assay,
            "filtered_genes": filtered_genes,
            "germline_genes": germline_genes,
            "is_public": True,
        }

    def asp_genes_payload(self, asp_id: str) -> dict[str, Any]:
        """Return public gene metadata for an assay panel."""
        gene_symbols, germline_gene_symbols = self.assay_panel_repository.get_asp_genes(asp_id)
        gene_details = list(
            self.hgnc_repository.get_metadata_by_symbols(list(gene_symbols or [])) or []
        )
        asp = self.assay_panel_repository.get_asp(asp_id) or {}
        catalog = self._catalog_category_for_asp(asp_id)
        return {
            "asp_id": asp_id,
            "asp": asp,
            "catalog": catalog,
            "stats": {
                "covered_total": len(gene_symbols or []),
                "germline_total": len(germline_gene_symbols or []),
                "displayed_total": len(gene_details),
            },
            "gene_details": gene_details,
            "germline_gene_symbols": list(germline_gene_symbols or []),
        }

    def _catalog_category_for_asp(self, asp_id: str) -> dict[str, Any]:
        """Return the public catalog category metadata for an ASP."""
        catalog = self.load_catalog()
        matches: list[dict[str, Any]] = []
        for modality_key, modality in (catalog.get("modalities") or {}).items():
            for category_key, category in (modality.get("categories") or {}).items():
                if str(category.get("asp_id") or "").strip() != asp_id:
                    continue
                matches.append(
                    {
                        "modality": modality_key,
                        "modality_label": modality.get("label") or modality_key,
                        "category_key": category_key,
                        **category,
                    }
                )
        if not matches:
            return {}
        for match in matches:
            if match.get("catalog_id") == asp_id or match.get("category_key") == asp_id:
                return match
        return matches[0]

    def assay_catalog_gene_symbols_payload(self, isgl_key: str) -> dict[str, Any]:
        """Return gene symbols for a public assay-catalog genelist."""
        isgl = self.gene_list_repository.get_isgl(isgl_key) or {}
        gene_symbols = set(sorted(isgl.get("genes", []))) if isgl_key else set()
        return {"gene_symbols": sorted(gene_symbols)}

    def isgl_genes_for_matrix(self, isgl_key: str) -> set[str]:
        """Return active public genelist genes for the assay matrix."""
        isgl_doc = (
            self.gene_list_repository.get_isgl(isgl_key, is_active=True, is_public=True) or {}
        )
        return set(isgl_doc.get("genes") or [])

    @measured_operation("query.assay_catalog_matrix")
    def assay_catalog_matrix_payload(
        self,
        *,
        page: int = 1,
        per_page: int = 100,
        gene: str | None = None,
    ) -> dict[str, Any]:
        """Return a paged public assay-catalog matrix payload."""
        catalog = self.load_catalog()
        modalities = catalog.get("modalities") or {}
        order = self.modalities_order() or list(modalities.keys())
        page = max(int(page or 1), 1)
        per_page = min(max(int(per_page or 100), 1), 500)
        gene_query = str(gene or "").strip()

        columns: list[dict[str, Any]] = []
        mod_spans: dict[str, int] = {}
        cat_spans: dict[str, int] = {}
        all_genes: set[str] = set()
        column_genes: list[tuple[dict[str, Any], set[str]]] = []

        for mod_key in order:
            mod_data = modalities.get(mod_key) or {}
            categories = mod_data.get("categories") or {}
            modality_total = 0

            for cat_key, cat_data in categories.items():
                asp_id = cat_data.get("asp_id")
                gene_lists = cat_data.get("gene_lists") or []
                real_lists = [gl for gl in gene_lists if gl.get("key")]
                cat_label = cat_data.get("label") or cat_data.get("title") or cat_key
                assay_label = cat_data.get("asp_id") or cat_data.get("catalog_id") or cat_label
                subpanel_label = cat_data.get("subpanel_id") or SUBPANEL_BASE_ID

                if not real_lists:
                    cat_spans[f"{mod_key}::{cat_key}"] = 1
                    modality_total += 1
                    col = {
                        "mod": mod_key,
                        "cat": cat_key,
                        "family": str(cat_data.get("family") or cat_data.get("asp_family") or ""),
                        "assay_group": str(cat_data.get("assay_group") or cat_label),
                        "assay": str(assay_label),
                        "subpanel": str(subpanel_label),
                        "cat_label": str(cat_label),
                        "isgl_key": f"__none__::{mod_key}::{cat_key}",
                        "isgl_label": "-",
                        "placeholder": True,
                    }
                    columns.append(col)
                    column_genes.append((col, set()))
                    continue

                cat_spans[f"{mod_key}::{cat_key}"] = len(real_lists)
                modality_total += len(real_lists)

                for gl in real_lists:
                    isgl_key = gl["key"]
                    isgl_label = gl.get("label") or isgl_key
                    if (asp_id and asp_id == isgl_key) or isgl_key == "single_gene":
                        genes_here = set(self._covered_genes(asp_id)[0])
                    else:
                        genes_here = self.isgl_genes_for_matrix(isgl_key)
                    col = {
                        "mod": mod_key,
                        "cat": cat_key,
                        "family": str(cat_data.get("family") or cat_data.get("asp_family") or ""),
                        "assay_group": str(cat_data.get("assay_group") or cat_label),
                        "assay": str(assay_label),
                        "subpanel": str(subpanel_label),
                        "cat_label": str(cat_label),
                        "isgl_key": isgl_key,
                        "isgl_label": isgl_label,
                        "placeholder": False,
                    }
                    columns.append(col)
                    column_genes.append((col, genes_here))
                    all_genes |= genes_here

            if not categories and modality_total == 0:
                placeholder_key = f"__none__::{mod_key}"
                col = {
                    "mod": mod_key,
                    "cat": "__none__",
                    "family": "",
                    "assay_group": str(mod_data.get("label") or mod_key),
                    "assay": "-",
                    "subpanel": SUBPANEL_BASE_ID,
                    "cat_label": str(mod_data.get("label") or mod_key),
                    "isgl_key": placeholder_key,
                    "isgl_label": "-",
                    "placeholder": True,
                }
                columns.append(col)
                column_genes.append((col, set()))
                mod_spans[mod_key] = 1
                cat_spans[f"{mod_key}::__none__"] = 1
            else:
                mod_spans[mod_key] = modality_total if modality_total > 0 else 1

        sorted_genes = sorted(all_genes)
        if gene_query:
            needle = gene_query.upper()
            filtered_genes = [item for item in sorted_genes if needle in item.upper()]
        else:
            filtered_genes = sorted_genes

        total = len(filtered_genes)
        if gene_query:
            visible_genes = filtered_genes[: min(total, 500)]
            page = 1
            per_page = len(visible_genes) or per_page
        else:
            start = (page - 1) * per_page
            visible_genes = filtered_genes[start : start + per_page]

        matrix: dict[str, dict[str, Any]] = {}
        visible_set = set(visible_genes)
        for col, genes_here in column_genes:
            if col.get("placeholder"):
                continue
            mod_key = col["mod"]
            cat_key = col["cat"]
            isgl_key = col["isgl_key"]
            for gene_symbol in visible_set.intersection(genes_here):
                matrix.setdefault(gene_symbol, {}).setdefault(mod_key, {}).setdefault(cat_key, {})[
                    isgl_key
                ] = True

        for gene_symbol in visible_genes:
            for col in columns:
                matrix.setdefault(gene_symbol, {}).setdefault(col["mod"], {}).setdefault(
                    col["cat"], {}
                ).setdefault(col["isgl_key"], False)

        return {
            "modalities": modalities,
            "order": order,
            "columns": columns,
            "mod_spans": mod_spans,
            "cat_spans": cat_spans,
            "genes": visible_genes,
            "matrix": matrix,
            "page": page,
            "per_page": per_page,
            "total": total,
            "search": gene_query,
            "has_next": (page * per_page) < total if not gene_query else False,
            "has_previous": page > 1 and not gene_query,
        }
