#  Copyright (c) 2025 Coyote3 Project Authors
#  All rights reserved.
#
#  This source file is part of the Coyote3 codebase.
#  The Coyote3 project provides a framework for genomic data analysis,
#  interpretation, reporting, and clinical diagnostics.
#
#  Unauthorized use, distribution, or modification of this software or its
#  components is strictly prohibited without prior written permission from
#  the copyright holders.
#

from __future__ import annotations
from flask import current_app as app
from coyote.extensions import store
from typing import Optional, List, Dict, Any, Tuple
import yaml
from pathlib import Path


class PublicUtility:
    """
    PublicUtility provides static utility methods for processing and presenting the Assay Catalog.

    Key features:
    - Loads and caches the assay catalog from YAML as-is.
    - Supports hierarchical navigation: modalities → categories → gene lists.
    - Provides normalized access to modalities (WGS, WTS, GenePanels) and their categories.
    - Supplies data structures for UI rendering, with parent-field inheritance for missing values.
    - Handles gene list resolution and overlap calculations for display and reporting.
    """

    DEFAULT_ENV = "production"

    # ----------------- Catalog loading -----------------

    @staticmethod
    def load_catalog() -> Dict[str, Any]:
        """
        Load and cache the assay catalog from the YAML file as-is.

        Returns:
            Dict[str, Any]: The loaded assay catalog as a dictionary. If the file is missing or empty, returns an empty dict.

        Notes:
            - The catalog is cached on the Flask app object to avoid repeated disk reads.
            - The YAML file path is taken from the Flask config key 'ASSAY_CATALOG_YAML', defaulting to 'assay_catalog.yaml'.
        """
        if not hasattr(app, "_assay_catalog_cache"):
            path = app.config.get("ASSAY_CATALOG_YAML", "assay_catalog.yaml")
            with open(Path(path), "r", encoding="utf-8") as fh:
                app._assay_catalog_cache = yaml.safe_load(fh) or {}
        return app._assay_catalog_cache or {}

    @staticmethod
    def modalities_order() -> List[str]:
        cat = PublicUtility.load_catalog()
        order = (cat.get("layout") or {}).get("order") or []
        return order or list((cat.get("modalities") or {}).keys())

    @staticmethod
    def normalize_mod(mod: Optional[str]) -> Optional[str]:
        """
        Accept friendly aliases; normalize to exact modality keys: 'WGS'|'WTS'|'GenePanels'
        Args:
            mod (Optional[str]): A modality name or alias (e.g., 'wgs', 'WTS', 'panels', etc.).

        Returns:
            Optional[str]: The normalized modality key ('WGS', 'WTS', or 'GenePanels'), or None if not recognized.
        """
        if not mod:
            return None
        v = (mod or "").strip().lower()
        if v == "wgs":
            return "WGS"
        if v == "wts":
            return "WTS"
        if v in ("panels", "panel", "genepanels", "gene-panels", "genepanel"):
            return "GenePanels"
        if mod in (PublicUtility.load_catalog().get("modalities") or {}):
            return mod
        return None

    @staticmethod
    def modality_block(mod: str) -> Optional[Dict[str, Any]]:
        """
        Return the raw modality block for the given modality key.
        Args:
            mod (str): The modality key (e.g., 'WGS', 'WTS', 'GenePanels').
        Returns:
            Optional[Dict[str, Any]]: The modality definition dict if found, otherwise None.
        """
        return (PublicUtility.load_catalog().get("modalities") or {}).get(mod)

    @staticmethod
    def categories_for(mod: str) -> List[Dict[str, Any]]:
        """
        Return categories for the given modality as a list of dicts.

        Args:
            mod (str): The modality key (e.g., 'WGS', 'WTS', 'GenePanels').

        Returns:
            List[Dict[str, Any]]: List of category dicts with keys 'catalog_id', 'label', and 'node' (the raw YAML fragment).
        """
        m = PublicUtility.modality_block(mod) or {}
        cats = m.get("categories") or {}
        out: List[Dict[str, Any]] = []
        for k, c in cats.items():
            out.append(
                {
                    "catalog_id": c.get("catalog_id") or k,
                    "label": c.get("label") or k,
                    "node": c,
                }
            )
        return out

    @staticmethod
    def category_def(mod: str, cat_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the raw category definition for the given modality and category ID.
        Match by catalog_id or by key.
        Args:
            mod (str): The modality key (e.g., 'WGS', 'WTS', 'GenePanels').
            cat_id (str): The category ID to look up (matches catalog_id or key).
        Returns:
            Optional[Dict[str, Any]]: The category definition dict if found, otherwise None.

        """
        m = PublicUtility.modality_block(mod) or {}
        cats = m.get("categories") or {}
        for k, c in cats.items():
            if cat_id == (c.get("catalog_id") or k) or cat_id == k:
                return c
        return None

    # ----------------- Hydration (right pane) -----------------

    @staticmethod
    def _fetch_aspc(aspc_ids: Optional[Dict[str, str]], env: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the ASPC (assay configuration) for the given environment from the aspc_ids mapping.
        Args:
            aspc_ids (Optional[Dict[str, str]]): Mapping of environment names to ASPC IDs.
            env (str): The environment to use for ASPC lookup (e.g., "production", "development").
        Returns:
            Optional[Dict[str, Any]]: The ASPC document if found, otherwise None.
        """
        if not aspc_ids:
            return None
        aspc_id = aspc_ids.get(env)
        if not aspc_id:
            return None
        return store.aspc_handler.get_aspc_with_id(aspc_id)

    @staticmethod
    def hydrate_category(
        mod: str, cat_id: str, gl_id: str = None, env: str = DEFAULT_ENV
    ) -> Optional[Dict[str, Any]]:
        """
        Build the data the right pane needs for a CATEGORY.

        Args:
            mod (str): The modality key (e.g., 'WGS', 'WTS', 'GenePanels').
            cat_id (str): The category ID within the modality.
            gl_id (str): The gene list ID within the category.
            env (str, optional): The environment to use for ASPC lookup (default: "production").

        Returns:
            Optional[Dict[str, Any]]: Dictionary with category display fields (catalog_id, label, description, input_material, tat, sample_modes, analysis, asp_id, asp, gene_lists).
            Returns None if the category is not found.

        Notes:
            - Covered genes are not included for weight; they are fetched lazily when drawing the table.
            - Analysis is sourced ONLY from ASPC (report_sections preferred).
        """
        node = PublicUtility.category_def(
            mod,
            cat_id,
        )
        if not node:
            return None

        gl_node = {}
        gene_lists = node.get("gene_lists") or []
        if gl_id:
            for gl in gene_lists:
                if gl_id == (gl.get("key") or gl.get("catalog_id")):
                    gl_node = gl
                    break

        asp_id = node.get("asp_id")
        aspc_ids = node.get("aspc_ids") or {}

        asp = store.asp_handler.get_asp(asp_id) if asp_id else None
        aspc = PublicUtility._fetch_aspc(aspc_ids, env) if aspc_ids else None

        analysis = []
        if aspc:
            analysis = aspc.get("report_sections") or []

        return {
            "catalog_id": node.get("catalog_id") or cat_id,
            "label": gl_node.get("label", node.get("label", cat_id)),
            "description": gl_node.get("description", node.get("description", "")),
            "input_material": gl_node.get("input_material", node.get("input_material")),
            "tat": gl_node.get("tat", node.get("tat")),
            "sample_modes": gl_node.get("sample_modes", node.get("sample_modes", [])),
            "analysis": gl_node.get("analysis", analysis),  # ASPC only
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
            "gene_lists": node.get("gene_lists", []) or [],  # [{key,label}...], AS-IS from YAML
        }

    @staticmethod
    def hydrate_modality(mod: str) -> Dict[str, Any]:
        """
        Prepare the data structure required for displaying a MODALITY (e.g., WGS, WTS, GenePanels) in the right pane.

        Args:
            mod (str): The modality key to display (e.g., 'WGS', 'WTS', 'GenePanels').

        Returns:
            Dict[str, Any]: Dictionary with modality display fields (label, description, input_material, tat, sample_modes, analysis, asp_id, asp).
            If certain fields are missing at the modality level, inherit them from the first category within that modality.
        """
        mb = PublicUtility.modality_block(mod) or {}

        return {
            "label": mb.get("label", mod),
            "description": mb.get("description", ""),
            "input_material": mb.get("input_material"),
            "tat": mb.get("tat"),
            "sample_modes": mb.get("sample_modes", []),
            "analysis": mb.get("analysis", []),
            "asp_id": mb.get("asp_id"),
            "asp": mb.get("asp"),
        }

    # ----------------- Genes & overlap -----------------

    @staticmethod
    def _covered_genes(asp_id: Optional[str]) -> Tuple[List[str], List[str]]:
        """
        Return a tuple of (`covered_genes`, `germline_genes`) symbols for the given ASP ID.

        Args:
            asp_id (Optional[str]): The ASP (assay) ID to fetch gene symbols for.

        Returns:
            Tuple[List[str], List[str]]:
                - covered_genes: List of gene symbols covered by the ASP.
                - germline_genes: List of germline gene symbols for the ASP.
            If `asp_id` is None or not found, returns two empty lists.
        """
        if not asp_id:
            return [], []
        genes, germ = store.asp_handler.get_asp_genes(asp_id)  # (list, list)
        return list(genes or []), list(germ or [])

    @staticmethod
    def resolve_gene_table(
        asp_id: Optional[str], isgl_key: Optional[str]
    ) -> Tuple[str, List[Dict[str, Any]], Dict[str, int]]:
        """
        Decide which gene table to show based on provided arguments.

        Args:
            asp_id (Optional[str]): The ASP (assay) ID to fetch covered genes from.
            isgl_key (Optional[str]): The ISGL (gene list) key to determine overlap with ASP covered genes.

        Returns:
            Tuple[str, List[Dict[str, Any]], Dict[str, int]]:
                - mode: One of 'covered', 'overlap', or 'genelist' indicating the table type.
                - hgnc_rows: List of gene metadata dicts for display.
                - stats: Dictionary with counts for total, covered, germline, and ISGL genes.
        """

        covered, germ = PublicUtility._covered_genes(asp_id)

        if isgl_key:
            isgl = store.isgl_handler.get_isgl(isgl_key) or {}
            isgl_genes = list(isgl.get("genes", []) or [])
            if covered:
                show = sorted(set(isgl_genes).intersection(set(covered)))
                mode = "overlap"
            else:
                show = sorted(set(isgl_genes))
                mode = "genelist"
            rows_raw = store.hgnc_handler.get_metadata_by_symbols(show) if show else []
            rows = PublicUtility._merge_with_placeholders(show, rows_raw)

            return (
                mode,
                rows,
                {
                    "total": len(show),
                    "isgl_total": len(isgl_genes),
                    "covered_total": len(covered),
                    "germline_total": len(germ),
                },
            )

        # default: covered genes
        show = sorted(set(covered))
        rows_raw = store.hgnc_handler.get_metadata_by_symbols(show) if show else []
        rows = PublicUtility._merge_with_placeholders(show, rows_raw)

        return (
            "covered",
            rows,
            {
                "total": len(show),
                "covered_total": len(covered),
                "germline_total": len(germ),
            },
        )

    @staticmethod
    def _hgnc_placeholder(symbol: str) -> Dict[str, Any]:
        """
        Return a dict shaped like an HGNC gene document, but empty/neutral,
        for symbols we couldn't resolve.

        Args:
            symbol (str): The gene symbol to use for the placeholder.

        Returns:
            Dict[str, Any]: A dictionary matching the HGNC schema, filled with neutral values,
            ensuring consistent columns for unmatched genes in the UI/CSV.
        """
        s = (symbol or "").strip()
        # minimal neutral values, matching your sample schema
        return {
            "_id": "HGNC:",  # unknown HGNC doc id
            "hgnc_id": "HGNC:",  # e.g., "HGNC:33164" if known
            "hgnc_symbol": s,  # we still show the requested symbol
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
            # keep compat aliases some codepaths use
            "symbol": s,
        }

    @staticmethod
    def _merge_with_placeholders(
        symbols: List[str], rows: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Ensure that every symbol in the `symbols` list appears in the `rows` list.

        Args:
            symbols (List[str]): List of gene symbols to ensure are present in the output.
            rows (List[Dict[str, Any]]): List of HGNC gene metadata dicts, possibly incomplete.

        Returns:
            List[Dict[str, Any]]: List of gene metadata dicts, including placeholders for missing symbols,
            sorted alphabetically by display symbol.
        """
        # symbols we already have (case-insensitive)
        have = set()
        out_rows: List[Dict[str, Any]] = rows or []
        for r in out_rows:
            sym = (r.get("hgnc_symbol") or r.get("symbol") or "").strip()
            if sym:
                have.add(sym.upper())

        # add placeholders for missing
        for s in symbols or []:
            if not s:
                continue
            if s.upper() not in have:
                out_rows.append(PublicUtility._hgnc_placeholder(s))

        # final sort by gene symbol
        out_rows = sorted(
            out_rows, key=lambda g: (g.get("hgnc_symbol") or g.get("symbol") or "").upper()
        )
        return out_rows

    @staticmethod
    def apply_drug_info(genes: dict[list], druglist_name: str = None) -> dict[list, Any]:

        drug_genes = store.isgl_handler.get_isgl(druglist_name) or {}
        drug_symbols = set(drug_genes.get("genes", [])) if drug_genes else set()
        for gene in genes:
            symbol = gene.get("hgnc_symbol") or gene.get("symbol") or ""
            gene["drug_target"] = symbol in drug_symbols

        return genes
