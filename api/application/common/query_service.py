"""Common query service used by router endpoints."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from api.application.interpretation.report_summary import enrich_reported_variant_docs
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
    ) -> None:
        """Create the service with explicit injected repositories."""
        self.hgnc_repository = hgnc_repository
        self.oncokb_repository = oncokb_repository
        self.variant_repository = variant_repository
        self.reported_variant_repository = reported_variant_repository
        self.assay_panel_repository = assay_panel_repository
        self.annotation_repository = annotation_repository
        self.sample_repository = sample_repository

    def gene_info_payload(self, gene_id: str) -> dict[str, Any]:
        """Return gene metadata by HGNC id or symbol."""
        normalized_gene_id = str(gene_id or "").strip()
        if normalized_gene_id.isnumeric() or normalized_gene_id.upper().startswith("HGNC:"):
            gene = self.hgnc_repository.get_metadata_by_hgnc_id(hgnc_id=normalized_gene_id)
        elif hasattr(self.hgnc_repository, "get_metadata_by_symbol_or_alias"):
            gene = self.hgnc_repository.get_metadata_by_symbol_or_alias(symbol=normalized_gene_id)
        else:
            gene = self.hgnc_repository.get_metadata_by_symbol(symbol=normalized_gene_id)
        symbol = (gene or {}).get("hgnc_symbol") or (gene or {}).get("symbol") or normalized_gene_id
        oncokb_gene = self.oncokb_repository.get_oncokb_gene(str(symbol).upper())
        return {
            "gene": gene,
            "query": {
                "input": normalized_gene_id,
                "resolved_symbol": symbol,
                "symbol_changed": bool(
                    normalized_gene_id
                    and symbol
                    and normalized_gene_id.upper() != str(symbol).upper()
                    and not normalized_gene_id.upper().startswith("HGNC:")
                ),
            },
            "knowledgebase": {
                "oncokb": oncokb_gene,
                "oncokb_url": f"https://www.oncokb.org/gene/{symbol}" if oncokb_gene else None,
            },
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
