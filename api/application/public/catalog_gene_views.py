"""Gene-table and coverage-matrix composition for the public catalog."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from api.application.resources.availability import available_panels
from api.contracts.schemas.public_catalog import clean_catalog_html


class PublicCatalogGeneViewsMixin:
    """Compose gene detail, list, and matrix projections for a public catalog service."""

    def _public_genelist(self, key: str) -> dict[str, Any]:
        """Resolve only explicitly public, active, non-case-specific gene lists."""
        document = self.gene_list_repository.get_isgl(key, is_active=True, is_public=True)
        if (
            not document
            or document.get("is_public") is not True
            or document.get("is_active") is not True
            or document.get("adhoc")
        ):
            return {}
        available = {panel["asp_id"] for panel in available_panels(self.assay_panel_repository)}
        if not available.intersection(document.get("asp_ids") or []):
            return {}
        document = {**document, "asp_ids": [key for key in document["asp_ids"] if key in available]}
        return {
            key: clean_catalog_html(value)
            if key == "description" and isinstance(value, str)
            else value
            for key, value in document.items()
            if key
            in {
                "isgl_id",
                "name",
                "display_name",
                "description",
                "genes",
                "asp_ids",
                "diagnosis",
                "list_type",
                "is_public",
                "is_active",
            }
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
        if asp_id not in {p["asp_id"] for p in available_panels(self.assay_panel_repository)}:
            return [], []
        genes, germline = self.assay_panel_repository.get_asp_genes(asp_id)
        return list(genes or []), list(germline or [])

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

    def knowledgebase_gene_markers(self, genes: list[str]) -> dict[str, dict[str, Any]]:
        """Return sanitized source-membership markers for public gene views."""
        symbols = sorted({str(gene).strip() for gene in genes if str(gene).strip()})
        if not symbols:
            return {}

        def records(repository: Any, method: str = "get_gene_records") -> dict[str, Any]:
            """Fetch the enclosing symbol batch when an optional repository supports it.

            Args:
                repository: Knowledgebase repository, or None when unavailable.
                method: Batch lookup method name, defaulting to get_gene_records.

            Returns:
                Lookup mapping or an empty mapping without a callable method.
            """
            getter = getattr(repository, method, None)
            return getter(symbols) if callable(getter) else {}

        oncokb = records(getattr(self, "oncokb_public_cache_repository", None))
        clinpgx = records(getattr(self, "clinpgx_public_repository", None))
        civic = records(getattr(self, "civic_repository", None))
        cosmic = records(
            getattr(self, "cosmic_repository", None),
            "get_cancer_gene_census_records",
        )
        markers: dict[str, dict[str, Any]] = {}
        for symbol in symbols:
            pgx = clinpgx.get(symbol) or clinpgx.get(symbol.upper()) or {}
            markers[symbol] = {
                "oncokb": bool(oncokb.get(symbol) or oncokb.get(symbol.upper())),
                "cosmic_cgc": bool(cosmic.get(symbol) or cosmic.get(symbol.upper())),
                "civic": bool(civic.get(symbol) or civic.get(symbol.upper())),
                "clinpgx": bool(pgx),
                "clinpgx_accession": pgx.get("pharmgkb_accession_id"),
            }
        return markers

    def apply_knowledgebase_gene_markers(self, genes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Attach public source-membership markers to gene rows in one batch."""
        symbols = [
            str(gene.get("resolved_symbol") or gene.get("hgnc_symbol") or gene.get("symbol") or "")
            for gene in genes
        ]
        markers = self.knowledgebase_gene_markers(symbols)
        for gene, symbol in zip(genes, symbols, strict=True):
            gene["knowledgebase_markers"] = markers.get(symbol, {})
        return genes

    def genelist_view_context(
        self, genelist_id: str, assay: str | None = None
    ) -> dict[str, Any] | None:
        """Return public view context for a genelist."""
        genelist = self._public_genelist(genelist_id)
        if not genelist:
            return None

        selected_assay = assay
        all_genes = genelist.get("genes", [])
        asp_ids = genelist.get("asp_ids", [])
        if selected_assay and selected_assay not in asp_ids:
            return None

        filtered_genes = all_genes
        germline_genes: list[str] = []
        if selected_assay and selected_assay in asp_ids:
            panel = self.assay_panel_repository.get_asp(selected_assay)
            panel_genes = panel.get("covered_genes", []) if panel else []
            germline_genes = panel.get("germline_genes", []) if panel else []
            filtered_genes = (
                sorted(set(all_genes).intersection(panel_genes))
                if panel and panel.get("asp_family") not in {"wgs", "wts"}
                else all_genes
            )

        return {
            "genelist": genelist,
            "selected_assay": selected_assay,
            "filtered_genes": filtered_genes,
            "germline_genes": germline_genes,
            "is_public": True,
            "gene_markers": self.knowledgebase_gene_markers(filtered_genes),
        }

    def asp_genes_payload(self, asp_id: str) -> dict[str, Any]:
        """Return public gene metadata for an assay panel."""
        if asp_id not in {p["asp_id"] for p in available_panels(self.assay_panel_repository)}:
            from api.domain.common.errors import api_error

            raise api_error(404, "Public assay is unavailable")
        gene_symbols, germline_gene_symbols = self._covered_genes(asp_id)
        gene_details = list(
            self.hgnc_repository.get_metadata_by_symbols(list(gene_symbols or [])) or []
        )
        gene_details = self._merge_with_placeholders(gene_symbols, gene_details)
        asp = self.assay_panel_repository.get_asp(asp_id) or {}
        asp = {**asp, "description": clean_catalog_html(str(asp.get("description") or ""))}
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
            "gene_details": self.apply_knowledgebase_gene_markers(gene_details),
            "germline_gene_symbols": list(germline_gene_symbols or []),
        }

    def _catalog_category_for_asp(self, asp_id: str) -> dict[str, Any]:
        """Return the first approved offering for an assay, or no catalog metadata."""
        return next(
            (
                item
                for item in self.published_offerings()["offerings"]
                if item["assay_id"] == asp_id
            ),
            {},
        )

    def assay_catalog_gene_symbols_payload(self, isgl_key: str) -> dict[str, Any]:
        """Return effective genes from published offerings using the selected list."""
        gene_symbols = {
            gene
            for item in self.published_offerings()["offerings"]
            for scope in item["gene_scopes"]
            if scope["list_id"] == isgl_key
            for gene in scope["genes"]
        }
        return {"gene_symbols": sorted(gene_symbols)}
