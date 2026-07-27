"""Common query service used by router endpoints."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.application.interpretation.report_summary import enrich_reported_variant_docs
from api.config.application_metadata import oncokb_gene_url
from api.domain.common.errors import api_error
from api.domain.core.dna.variant_identity import (
    build_simple_id_hash_from_simple_id,
    normalize_simple_id,
)


class CommonQueryService:
    """Provide shared gene and tiered-variant query workflows."""

    @classmethod
    def from_store(cls, store: Any) -> "CommonQueryService":
        """Build the service from the runtime store."""
        return cls(
            hgnc_repository=store.hgnc_repository,
            oncokb_repository=store.oncokb_repository,
            variant_repository=store.variant_repository,
            reported_variant_repository=store.reported_variant_repository,
            assay_panel_repository=store.assay_panel_repository,
            annotation_repository=store.annotation_repository,
            sample_repository=store.sample_repository,
            oncokb_public_cache_repository=getattr(store, "oncokb_public_cache_repository", None),
            clinpgx_public_repository=getattr(store, "clinpgx_public_repository", None),
            civic_repository=getattr(store, "civic_repository", None),
            brca_repository=getattr(store, "brca_repository", None),
            iarc_tp53_repository=getattr(store, "iarc_tp53_repository", None),
            bam_record_repository=getattr(store, "bam_record_repository", None),
        )

    def __init__(
        self,
        *,
        hgnc_repository: Any,
        oncokb_repository: Any,
        variant_repository: Any,
        reported_variant_repository: Any,
        assay_panel_repository: Any,
        annotation_repository: Any,
        sample_repository: Any,
        oncokb_public_cache_repository: Any | None = None,
        clinpgx_public_repository: Any | None = None,
        civic_repository: Any | None = None,
        brca_repository: Any | None = None,
        iarc_tp53_repository: Any | None = None,
        bam_record_repository: Any | None = None,
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.hgnc_repository = hgnc_repository
        self.oncokb_repository = oncokb_repository
        self.variant_repository = variant_repository
        self.reported_variant_repository = reported_variant_repository
        self.assay_panel_repository = assay_panel_repository
        self.annotation_repository = annotation_repository
        self.sample_repository = sample_repository
        self.oncokb_public_cache_repository = oncokb_public_cache_repository
        self.clinpgx_public_repository = clinpgx_public_repository
        self.civic_repository = civic_repository
        self.brca_repository = brca_repository
        self.iarc_tp53_repository = iarc_tp53_repository
        self.bam_record_repository = bam_record_repository

    def _resolve_gene(self, gene_id: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        """Resolve a gene identifier through HGNC id, current symbol, previous symbol, or alias."""
        normalized_gene_id = str(gene_id or "").strip()
        if normalized_gene_id.isnumeric() or normalized_gene_id.upper().startswith("HGNC:"):
            gene = self.hgnc_repository.get_metadata_by_hgnc_id(hgnc_id=normalized_gene_id)
        elif hasattr(self.hgnc_repository, "get_metadata_by_symbol_or_alias"):
            gene = self.hgnc_repository.get_metadata_by_symbol_or_alias(symbol=normalized_gene_id)
        else:
            gene = self.hgnc_repository.get_metadata_by_symbol(symbol=normalized_gene_id)
        symbol = (gene or {}).get("hgnc_symbol") or (gene or {}).get("symbol") or normalized_gene_id
        query = {
            "input": normalized_gene_id,
            "resolved_symbol": symbol,
            "symbol_changed": bool(
                normalized_gene_id
                and symbol
                and normalized_gene_id.upper() != str(symbol).upper()
                and not normalized_gene_id.upper().startswith("HGNC:")
            ),
        }
        return gene, query

    @staticmethod
    def _source_present(value: Any) -> bool:
        """Return true when a source has useful content for a response."""
        if value is None:
            return False
        if isinstance(value, dict | list | tuple | set):
            return bool(value)
        return True

    @classmethod
    def _available_sources(cls, sources: dict[str, Any]) -> list[str]:
        """Return source names that have non-empty payloads."""
        return sorted(name for name, value in sources.items() if cls._source_present(value))

    def gene_info_payload(self, gene_id: str) -> dict[str, Any]:
        """Return gene metadata by HGNC id or symbol."""
        gene, query = self._resolve_gene(gene_id)
        symbol = query["resolved_symbol"]
        oncokb_gene = self.oncokb_repository.get_oncokb_gene(str(symbol).upper())
        return {
            "gene": gene,
            "query": query,
            "knowledgebase": {
                "oncokb": oncokb_gene,
                "oncokb_url": oncokb_gene_url(symbol) if oncokb_gene else None,
            },
        }

    def knowledgebase_gene_payload(self, gene_id: str) -> dict[str, Any]:
        """Return aggregated external knowledgebase context for a gene."""
        gene, query = self._resolve_gene(gene_id)
        symbol = str(query["resolved_symbol"] or "").strip()
        upper_symbol = symbol.upper()

        public_oncokb_getter = getattr(self.oncokb_public_cache_repository, "get_gene_record", None)
        clinpgx_getter = getattr(self.clinpgx_public_repository, "get_gene_record", None)
        civic_getter = getattr(self.civic_repository, "get_civic_gene_info", None)
        sources = {
            "oncokb_public": public_oncokb_getter(symbol)
            if callable(public_oncokb_getter)
            else None,
            "oncokb_local": self.oncokb_repository.get_oncokb_gene(upper_symbol),
            "oncokb_actionable_local": self.oncokb_repository.get_oncokb_action_gene(upper_symbol),
            "clinpgx_public": clinpgx_getter(symbol) if callable(clinpgx_getter) else None,
            "civic_gene": civic_getter(symbol) if callable(civic_getter) else None,
            "brca_exchange": {
                "applies_to_gene": upper_symbol in {"BRCA1", "BRCA2"},
                "lookup": "variant-coordinate",
            },
            "iarc_tp53": {
                "applies_to_gene": upper_symbol == "TP53",
                "lookup": "variant-hgvsc",
            },
        }
        return {
            "query": query,
            "gene": gene,
            "sources": sources,
            "available_sources": self._available_sources(sources),
        }

    def knowledgebase_variant_payload(
        self,
        *,
        chrom: str,
        pos: int,
        ref: str,
        alt: str,
        gene: str,
        hgvsc: str | None = None,
        hgvsp: str | None = None,
        assay_group: str = "dna",
    ) -> dict[str, Any]:
        """Return local knowledgebase context for one variant identity."""
        selected_csq = {
            "SYMBOL": str(gene or "").strip(),
            "HGVSc": str(hgvsc or "").strip(),
            "HGVSp": str(hgvsp or "").strip(),
        }
        variant = {
            "CHROM": str(chrom or "").removeprefix("chr"),
            "POS": int(pos),
            "REF": str(ref or "").strip(),
            "ALT": str(alt or "").strip(),
            "INFO": {"selected_CSQ": selected_csq},
        }
        hgvsp_candidates = [selected_csq["HGVSp"]] if selected_csq["HGVSp"] else []
        sources = {
            "civic_variants": self.civic_repository.get_civic_data(variant, selected_csq["HGVSp"])
            if self.civic_repository is not None
            else [],
            "oncokb_local": self.oncokb_repository.get_oncokb_anno(variant, hgvsp_candidates)
            if hgvsp_candidates
            else None,
            "oncokb_actionable_local": self.oncokb_repository.get_oncokb_action(
                variant, hgvsp_candidates
            )
            if hgvsp_candidates
            else [],
            "brca_exchange": self.brca_repository.get_brca_data(variant, assay_group)
            if self.brca_repository is not None
            else None,
            "iarc_tp53": self.iarc_tp53_repository.find_iarc_tp53(variant)
            if self.iarc_tp53_repository is not None
            else None,
        }
        return {
            "query": {
                "chrom": variant["CHROM"],
                "pos": variant["POS"],
                "ref": variant["REF"],
                "alt": variant["ALT"],
                "gene": selected_csq["SYMBOL"],
                "hgvsc": selected_csq["HGVSc"] or None,
                "hgvsp": selected_csq["HGVSp"] or None,
                "assay_group": assay_group,
            },
            "variant": variant,
            "sources": sources,
            "available_sources": self._available_sources(sources),
        }

    def bam_files_payload(self, *, sample_ids: list[str]) -> dict[str, Any]:
        """Return BAM-service file paths for sample IDs."""
        normalized = [str(sample_id or "").strip() for sample_id in sample_ids]
        normalized = [sample_id for sample_id in normalized if sample_id]
        if not normalized:
            raise api_error(400, "At least one sample_id must be provided")
        if self.bam_record_repository is None:
            return {"query": {"sample_ids": normalized}, "bam_files": {}}
        lookup = {sample_id: sample_id for sample_id in normalized}
        return {
            "query": {"sample_ids": normalized},
            "bam_files": self.bam_record_repository.get_bams(lookup) or {},
        }

    def tiered_variant_context_payload(self, *, variant_id: str, tier: int) -> dict[str, Any]:
        """Return reported-variant context for a tiered variant."""
        variant = self.variant_repository.get_variant(variant_id)
        if not variant:
            raise api_error(404, "Variant not found")

        csq = variant.get("INFO", {}).get("selected_CSQ", {}) or {}
        gene = csq.get("SYMBOL")
        simple_id = normalize_simple_id(variant.get("simple_id"))
        simple_id_hash = variant.get("simple_id_hash") or (
            build_simple_id_hash_from_simple_id(simple_id) if simple_id else None
        )
        hgvsc = csq.get("HGVSc")
        hgvsp = csq.get("HGVSp")

        or_conditions: list[dict[str, Any]] = []
        if simple_id_hash:
            or_conditions.append({"simple_id_hash": simple_id_hash})
        elif simple_id:
            or_conditions.append({"simple_id": simple_id})
        elif hgvsc:
            or_conditions.append({"hgvsc": hgvsc})
        elif hgvsp:
            or_conditions.append({"hgvsp": hgvsp})

        if not gene or not or_conditions:
            return {
                "variant": variant,
                "docs": [],
                "tier": tier,
                "error": "Variant has insufficient identity fields",
            }

        query = {"gene": gene, "$or": or_conditions}
        docs = list(self.reported_variant_repository.list_reported_variants(query) or [])
        docs = enrich_reported_variant_docs(
            deepcopy(docs),
            sample_repository=self.sample_repository,
            annotation_repository=self.annotation_repository,
        )
        for doc in docs:
            sample_doc = doc.get("sample") or {}
            sample_oid = doc.get("sample_oid") or sample_doc.get("_id")
            if sample_oid is not None:
                doc["sample_id"] = str(sample_oid)
                sample_doc["sample_id"] = str(sample_oid)
            if sample_doc:
                doc["sample"] = sample_doc
        return {"variant": variant, "docs": docs, "tier": tier, "error": None}

    def _sample_reference(
        self,
        *,
        sample_oid: Any,
        sample_doc: dict[str, Any] | None,
        sample_name: str | None,
    ) -> dict[str, Any]:
        """Build the sample reference carried by common search payloads."""
        sample_id = str(sample_oid) if sample_oid is not None else None
        resolved_name = sample_name or (sample_doc or {}).get("name") or "UNKNOWN_SAMPLE"
        return {
            "sample_id": sample_id,
            "sample_name": resolved_name,
            "name": resolved_name,
            "assay": (sample_doc or {}).get("assay"),
            "subpanel": (sample_doc or {}).get("subpanel") or (sample_doc or {}).get("subpanel_id"),
            "profile": (sample_doc or {}).get("profile"),
            "report_oids": {},
        }

    def tiered_variant_search_payload(
        self,
        *,
        search_str: str | None,
        search_mode: str,
        include_annotation_text: bool,
        assays: list[str] | None,
        limit_entries: int,
    ) -> dict[str, Any]:
        """Search tiered variants and related annotations across reports."""
        assay_choices = list(self.assay_panel_repository.get_all_asp_groups() or [])
        effective_assays = assays if assays else None
        docs_found = list(
            self.annotation_repository.find_variants_by_search_string(
                search_str=search_str,
                search_mode=search_mode,
                include_annotation_text=include_annotation_text,
                assays=effective_assays,
                limit=limit_entries,
            )
            or []
        )
        reported_found = list(
            self.reported_variant_repository.find_reported_variants_by_search_string(
                search_str=search_str or "",
                search_mode=search_mode,
                assays=effective_assays,
                limit=limit_entries,
            )
            or []
        )

        tier_stats = {"total": {}, "by_assay": {}}
        if search_str:
            tier_stats = self.annotation_repository.get_tier_stats_by_search(
                search_str=search_str,
                search_mode=search_mode,
                include_annotation_text=include_annotation_text,
                assays=effective_assays,
            )

        sample_tagged_docs = []
        associated_annotation_text_oids: set[str] = set()
        reported_docs_seen: set[str] = set()

        for doc in docs_found:
            merged_doc = deepcopy(doc)
            if include_annotation_text and not merged_doc.get("text"):
                merged_doc["text"] = self.annotation_repository.get_matching_annotation_text(
                    merged_doc
                )
            sample_oids: dict[str, dict[str, Any]] = {}
            reported_docs = list(
                self.reported_variant_repository.list_reported_variants(
                    {"annotation_oid": {"$in": [doc["_id"], str(doc["_id"])]}}
                )
                or []
            )

            for reported_doc in reported_docs:
                if reported_doc.get("_id") is not None:
                    reported_docs_seen.add(str(reported_doc.get("_id")))
                sample_oid = reported_doc.get("sample_oid")
                report_oid = reported_doc.get("report_oid")
                annotation_text_oid = reported_doc.get("annotation_text_oid")
                report_id = reported_doc.get("report_id")
                sample_doc = self.sample_repository.get_sample_by_oid(sample_oid)
                sample_name = (
                    reported_doc.get("sample_name") or sample_doc.get("name")
                    if sample_doc
                    else None
                )
                report_num = reported_doc.get("report_num")

                if sample_oid:
                    sample_key = str(sample_oid)
                    if sample_key not in sample_oids:
                        sample_oids[sample_key] = self._sample_reference(
                            sample_oid=sample_oid,
                            sample_doc=sample_doc,
                            sample_name=sample_name,
                        )
                    if report_oid and report_id:
                        report_oids = sample_oids.get(sample_key, {}).get("report_oids", {})
                        if report_id not in report_oids:
                            sample_oids[sample_key]["report_oids"][report_id] = report_num

                if include_annotation_text and annotation_text_oid:
                    associated_annotation_text_oids.add(annotation_text_oid)
                    merged_doc["text"] = self.annotation_repository.get_annotation_text_by_oid(
                        annotation_text_oid
                    )

            merged_doc["reported_docs"] = reported_docs
            merged_doc["samples"] = sample_oids

            if merged_doc.get("_id") not in associated_annotation_text_oids:
                sample_tagged_docs.append(merged_doc)

        for reported_doc in reported_found:
            reported_doc_id = str(reported_doc.get("_id"))
            if reported_doc_id in reported_docs_seen:
                continue

            annotation_oid = reported_doc.get("annotation_oid")
            annotation_doc = (
                self.annotation_repository.get_annotation_by_oid(annotation_oid)
                if annotation_oid
                else None
            ) or {}
            sample_oid = reported_doc.get("sample_oid")
            sample_doc = (
                self.sample_repository.get_sample_by_oid(sample_oid) if sample_oid else None
            )
            sample_name = (
                reported_doc.get("sample_name")
                or (sample_doc or {}).get("name")
                or "UNKNOWN_SAMPLE"
            )
            report_id = reported_doc.get("report_id")
            report_num = reported_doc.get("report_num")
            sample_key = str(sample_oid) if sample_oid is not None else reported_doc_id

            merged_doc = {
                **annotation_doc,
                **reported_doc,
                "class": annotation_doc.get("class") or reported_doc.get("tier"),
                "author": annotation_doc.get("author") or reported_doc.get("created_by"),
                "samples": {
                    sample_key: {
                        **self._sample_reference(
                            sample_oid=sample_oid,
                            sample_doc=sample_doc,
                            sample_name=sample_name,
                        ),
                        "report_oids": {report_id: report_num} if report_id else {},
                    }
                },
                "reported_docs": [reported_doc],
            }
            if include_annotation_text and reported_doc.get("annotation_text_oid"):
                merged_doc["text"] = self.annotation_repository.get_annotation_text_by_oid(
                    reported_doc.get("annotation_text_oid")
                )
            elif include_annotation_text and not merged_doc.get("text"):
                merged_doc["text"] = self.annotation_repository.get_matching_annotation_text(
                    merged_doc
                )
            sample_tagged_docs.append(merged_doc)

        return {
            "docs": sample_tagged_docs,
            "search_str": search_str,
            "search_mode": search_mode,
            "include_annotation_text": include_annotation_text,
            "tier_stats": tier_stats,
            "assays": assays,
            "assay_choices": assay_choices,
        }


__all__ = ["CommonQueryService"]
