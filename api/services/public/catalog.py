"""Public assay catalog application service used by FastAPI public routes."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from api.runtime_state import app


class PublicCatalogService:
    """Provide public catalog workflows."""

    DEFAULT_ENV = "production"

    @classmethod
    def from_store(cls, store: Any) -> "PublicCatalogService":
        """Build the service from the shared store."""
        return cls(
            assay_configuration_handler=store.assay_configuration_handler,
            assay_panel_handler=store.assay_panel_handler,
            hgnc_handler=store.hgnc_handler,
            gene_list_handler=store.gene_list_handler,
        )

    def __init__(
        self,
        *,
        assay_configuration_handler: Any,
        assay_panel_handler: Any,
        hgnc_handler: Any,
        gene_list_handler: Any,
    ) -> None:
        """Create the service with explicit injected handlers."""
        self.assay_configuration_handler = assay_configuration_handler
        self.assay_panel_handler = assay_panel_handler
        self.hgnc_handler = hgnc_handler
        self.gene_list_handler = gene_list_handler

    @staticmethod
    def load_catalog() -> Dict[str, Any]:
        """Load and cache the public assay catalog.

        Returns:
            Dict[str, Any]: Parsed assay catalog data.
        """
        if not hasattr(app, "_assay_catalog_cache"):
            path = app.config.get("ASSAY_CATALOG_YAML", "assay_catalog.yaml")
            with open(Path(path), "r", encoding="utf-8") as fh:
                app._assay_catalog_cache = yaml.safe_load(fh) or {}
        return app._assay_catalog_cache or {}

    @staticmethod
    def modalities_order() -> List[str]:
        """Return the display order for catalog modalities.

        Returns:
            List[str]: Ordered modality keys.
        """
        catalog = PublicCatalogService.load_catalog()
        order = (catalog.get("layout") or {}).get("order") or []
        return order or list((catalog.get("modalities") or {}).keys())

    @staticmethod
    def normalize_mod(mod: Optional[str]) -> Optional[str]:
        """Normalize modality aliases to catalog keys.

        Args:
            mod: Raw modality value from the request.

        Returns:
            Optional[str]: Canonical modality key when recognized.
        """
        if not mod:
            return None
        value = (mod or "").strip().lower()
        if value == "wgs":
            return "WGS"
        if value == "wts":
            return "WTS"
        if value in ("panels", "panel", "genepanels", "gene-panels", "genepanel"):
            return "GenePanels"
        if mod in (PublicCatalogService.load_catalog().get("modalities") or {}):
            return mod
        return None

    @staticmethod
    def modality_block(mod: str) -> Optional[Dict[str, Any]]:
        """Return the catalog block for a modality.

        Args:
            mod: Canonical modality key.

        Returns:
            Optional[Dict[str, Any]]: Catalog block for the modality.
        """
        return (PublicCatalogService.load_catalog().get("modalities") or {}).get(mod)

    @staticmethod
    def categories_for(mod: str) -> List[Dict[str, Any]]:
        """Return category entries for a modality.

        Args:
            mod: Canonical modality key.

        Returns:
            List[Dict[str, Any]]: Category descriptors for the modality.
        """
        modality = PublicCatalogService.modality_block(mod) or {}
        categories = modality.get("categories") or {}
        out: List[Dict[str, Any]] = []
        for key, category in categories.items():
            out.append(
                {
                    "catalog_id": category.get("catalog_id") or key,
                    "label": category.get("label") or key,
                    "node": category,
                }
            )
        return out

    @staticmethod
    def category_def(mod: str, cat_id: str) -> Optional[Dict[str, Any]]:
        """Return the catalog definition for a modality category.

        Args:
            mod: Canonical modality key.
            cat_id: Category identifier to resolve.

        Returns:
            Optional[Dict[str, Any]]: Category definition when found.
        """
        modality = PublicCatalogService.modality_block(mod) or {}
        categories = modality.get("categories") or {}
        for key, category in categories.items():
            if cat_id == (category.get("catalog_id") or key) or cat_id == key:
                return category
        return None

    def _fetch_aspc(self, aspc_ids: Optional[Dict[str, str]], env: str) -> Optional[Dict[str, Any]]:
        """Resolve an assay-config document for a target environment.

        Args:
            aspc_ids: Environment-to-assay-config mapping.
            env: Environment to resolve.

        Returns:
            Optional[Dict[str, Any]]: Assay-config document when available.
        """
        if not aspc_ids:
            return None
        aspc_id = aspc_ids.get(env)
        if not aspc_id:
            return None
        return self.assay_configuration_handler.get_aspc_with_id(aspc_id)

    def hydrate_category(
        self, mod: str, cat_id: str, gl_id: str | None = None, env: str = DEFAULT_ENV
    ) -> Optional[Dict[str, Any]]:
        """Hydrate a public catalog category with runtime metadata.

        Args:
            mod: Canonical modality key.
            cat_id: Category identifier to resolve.
            gl_id: Optional gene-list identifier to focus on.
            env: Environment to use for assay-config lookup.

        Returns:
            Optional[Dict[str, Any]]: Hydrated category payload when found.
        """
        node = self.category_def(mod, cat_id)
        if not node:
            return None

        gl_node: Dict[str, Any] = {}
        gene_lists = node.get("gene_lists") or []
        if gl_id:
            for gl in gene_lists:
                if gl_id == (gl.get("key") or gl.get("catalog_id")):
                    gl_node = gl
                    break

        asp_id = node.get("asp_id")
        aspc_ids = node.get("aspc_ids") or {}

        asp = self.assay_panel_handler.get_asp(asp_id) if asp_id else None
        aspc = self._fetch_aspc(aspc_ids, env) if aspc_ids else None

        analysis = node.get("analysis", []) or []
        if aspc and not analysis:
            analysis = aspc.get("report_sections") or []

        return {
            "catalog_id": node.get("catalog_id") or cat_id,
            "label": gl_node.get("label", node.get("label", cat_id)),
            "description": gl_node.get("description", node.get("description", "")),
            "input_material": gl_node.get("input_material", node.get("input_material")),
            "tat": gl_node.get("tat", node.get("tat")),
            "sample_modes": gl_node.get("sample_modes", node.get("sample_modes", [])),
            "analysis": gl_node.get("analysis", analysis),
            "asp_id": asp_id,
            "asp": (
                None
                if not asp
                else {
                    "platform": asp.get("platform"),
                    "read_length": asp.get("read_length"),
                    "read_mode": asp.get("read_mode"),
                    "covered_genes_count": asp.get("covered_genes_count"),
                    "germline_genes_count": asp.get("germline_genes_count"),
                }
            ),
            "gene_lists": node.get("gene_lists", []) or [],
        }

    @staticmethod
    def hydrate_modality(mod: str) -> Dict[str, Any]:
        """Hydrate summary metadata for a modality.

        Args:
            mod: Canonical modality key.

        Returns:
            Dict[str, Any]: Hydrated modality payload.
        """
        modality = PublicCatalogService.modality_block(mod) or {}
        return {
            "label": modality.get("label", mod),
            "description": modality.get("description", ""),
            "input_material": modality.get("input_material"),
            "tat": modality.get("tat"),
            "sample_modes": modality.get("sample_modes", []),
            "analysis": modality.get("analysis", []),
            "asp_id": modality.get("asp_id"),
            "asp": modality.get("asp"),
        }

    def _covered_genes(self, asp_id: Optional[str]) -> Tuple[List[str], List[str]]:
        """Return covered and germline genes for an assay panel.

        Args:
            asp_id: Assay-panel identifier.

        Returns:
            Tuple[List[str], List[str]]: Covered and germline gene symbols.
        """
        if not asp_id:
            return [], []
        genes, germline = self.assay_panel_handler.get_asp_genes(asp_id)
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
            rows_raw = list(self.hgnc_handler.get_metadata_by_symbols(show) or []) if show else []
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
            isgl = self.gene_list_handler.get_isgl(isgl_key) or {}
            isgl_genes = list(isgl.get("genes", []) or [])
            if covered:
                show = sorted(set(isgl_genes).intersection(set(covered)))
                mode = "overlap"
            else:
                show = sorted(set(isgl_genes))
                mode = "genelist"
            rows_raw = list(self.hgnc_handler.get_metadata_by_symbols(show) or []) if show else []
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
        rows_raw = list(self.hgnc_handler.get_metadata_by_symbols(show) or []) if show else []
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
    def _hgnc_placeholder(symbol: str) -> Dict[str, Any]:
        """Hgnc placeholder.

        Args:
                symbol: Symbol.

        Returns:
                The  hgnc placeholder result.
        """
        cleaned = (symbol or "").strip()
        return {
            "_id": "HGNC:",
            "hgnc_id": "HGNC:",
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
        }

    @staticmethod
    def _merge_with_placeholders(
        symbols: List[str], rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge with placeholders.

        Args:
                symbols: Symbols.
                rows: Rows.

        Returns:
                The  merge with placeholders result.
        """
        have = set()
        out_rows: List[Dict[str, Any]] = rows or []
        for row in out_rows:
            symbol = (row.get("hgnc_symbol") or row.get("symbol") or "").strip()
            if symbol:
                have.add(symbol.upper())

        for symbol in symbols or []:
            if symbol and symbol.upper() not in have:
                out_rows.append(PublicCatalogService._hgnc_placeholder(symbol))

        return sorted(
            out_rows, key=lambda g: (g.get("hgnc_symbol") or g.get("symbol") or "").upper()
        )

    def apply_drug_info(
        self, genes: List[Dict[str, Any]], druglist_name: str | None = None
    ) -> List[Dict[str, Any]]:
        """Annotate genes with drug-target membership."""
        drug_genes = self.gene_list_handler.get_isgl(druglist_name) or {}
        drug_symbols = set(drug_genes.get("genes", [])) if drug_genes else set()
        for gene in genes:
            symbol = gene.get("hgnc_symbol") or gene.get("symbol") or ""
            gene["drug_target"] = symbol in drug_symbols
        return genes

    def genelist_view_context(
        self, genelist_id: str, assay: str | None = None
    ) -> dict[str, Any] | None:
        """Return public view context for a genelist."""
        genelist = self.gene_list_handler.get_isgl(genelist_id, is_active=True)
        if not genelist:
            return None

        selected_assay = assay
        all_genes = genelist.get("genes", [])
        assays = genelist.get("assays", [])

        filtered_genes = all_genes
        germline_genes: list[str] = []
        if selected_assay and selected_assay in assays:
            panel = self.assay_panel_handler.get_asp(selected_assay)
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
        gene_symbols, germline_gene_symbols = self.assay_panel_handler.get_asp_genes(asp_id)
        gene_details = list(
            self.hgnc_handler.get_metadata_by_symbols(list(gene_symbols or [])) or []
        )
        return {
            "asp_id": asp_id,
            "gene_details": gene_details,
            "germline_gene_symbols": list(germline_gene_symbols or []),
        }

    def assay_catalog_gene_symbols_payload(self, isgl_key: str) -> dict[str, Any]:
        """Return gene symbols for a public assay-catalog genelist."""
        isgl = self.gene_list_handler.get_isgl(isgl_key) or {}
        gene_symbols = set(sorted(isgl.get("genes", []))) if isgl_key else set()
        return {"gene_symbols": sorted(gene_symbols)}

    def isgl_genes_for_matrix(self, isgl_key: str) -> set[str]:
        """Return active public genelist genes for the assay matrix."""
        isgl_doc = self.gene_list_handler.get_isgl(isgl_key, is_active=True, is_public=True) or {}
        return set(isgl_doc.get("genes") or [])
